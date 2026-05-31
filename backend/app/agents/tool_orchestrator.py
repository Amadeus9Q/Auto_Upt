from __future__ import annotations

import logging
from datetime import UTC, datetime
import json
import re
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.registry import select_adapters
from backend.app.agents.content_analyst import ContentAnalystAgent
from backend.app.agents.orchestrator import SimulatedAgentOrchestrator
from backend.app.agents.platform_stylist import PLATFORM_STYLES, PlatformStylistAgent
from backend.app.agents.tools import AgentToolRegistry, build_default_tool_registry
from backend.app.core.config import get_settings
from backend.app.models.agent import AgentRunRecord
from backend.app.schemas.agent import (
    AgentAdaptPreviewRequest,
    AgentAdaptPreviewResponse,
    AgentGeneratedMetadata,
    AgentRewrittenContent,
    AgentToolCall,
    AgentToolListResponse,
)
from backend.app.schemas.content import PreviewCreateRequest
from backend.app.services.preview_service import PreviewService

logger = logging.getLogger(__name__)


class _LlmStatusTracker:
    """Track whether any LLM call was attempted and succeeded."""

    def __init__(self) -> None:
        self.attempted = False
        self.succeeded = False

    def on_attempt(self) -> None:
        self.attempted = True

    def on_success(self) -> None:
        self.succeeded = True


class ToolDrivenAgentOrchestrator:
    def __init__(
        self,
        session: AsyncSession,
        registry: AgentToolRegistry | None = None,
    ) -> None:
        self.session = session
        self.registry = registry or build_default_tool_registry()
        self.preview_service = PreviewService(session)
        self.content_analyst = ContentAnalystAgent()
        self.platform_stylist = PlatformStylistAgent()
        self.settings = get_settings()
        self._llm_tracker = _LlmStatusTracker()

    def list_tools(self) -> AgentToolListResponse:
        return AgentToolListResponse(tools=self.registry.list_tools())

    async def get_run(self, run_id: str) -> AgentAdaptPreviewResponse | None:
        record = await self.session.get(AgentRunRecord, run_id)
        if record is None:
            return None
        return AgentAdaptPreviewResponse.model_validate(record.result_payload)

    async def run_adapt_preview(self, request: AgentAdaptPreviewRequest) -> AgentAdaptPreviewResponse:
        run_id = str(uuid4())
        created_at = datetime.now(UTC)
        tool_calls: list[AgentToolCall] = []
        self._llm_tracker = _LlmStatusTracker()

        def call_tool(name: str, input_summary: str, runner) -> Any:
            started_at = datetime.now(UTC)
            output = runner()
            completed_at = datetime.now(UTC)
            tool = self.registry.get(name)
            serializable_output = self._jsonable(output)
            tool_calls.append(
                AgentToolCall(
                    name=name,
                    description=tool.description,
                    status="succeeded",
                    input_summary=input_summary,
                    output=serializable_output,
                    started_at=started_at,
                    completed_at=completed_at,
                )
            )
            return output

        content_ir = call_tool(
            "content.normalize",
            "用户输入的标题、正文、标签、素材和正文块。",
            lambda: self.preview_service.normalize_content(request),
        )
        analysis = call_tool(
            "content.analyze",
            "统一内容 IR 中的正文、标签和素材。",
            lambda: self.content_analyst.analyze(
                body=content_ir["body"],
                title=content_ir.get("title"),
                tags=content_ir.get("tags", []),
                content_blocks=content_ir.get("body_blocks", []),
                assets=content_ir.get("assets", []),
                content_type=content_ir.get("content_type", "article"),
            ),
        )
        metadata = call_tool(
            "metadata.extract",
            "内容分析结果、用户已有标题和关键词。",
            lambda: self._extract_metadata(request, analysis),
        )
        rewritten_content = call_tool(
            "style.rewrite",
            "原始正文、目标风格、改写强度和元数据建议。",
            lambda: self._rewrite_content(request, metadata),
        )

        preview_request = PreviewCreateRequest(
            title=rewritten_content.title,
            body=rewritten_content.body,
            content_type=request.content_type,
            tags=rewritten_content.tags,
            assets=request.assets,
            content_blocks=request.content_blocks,
            cover_asset_id=request.cover_asset_id,
            platforms=request.platforms,
        )
        adapted_content_ir = self.preview_service.normalize_content(preview_request)
        adapted_analysis = self.content_analyst.analyze(
            body=adapted_content_ir["body"],
            title=adapted_content_ir.get("title"),
            tags=adapted_content_ir.get("tags", []),
            content_blocks=adapted_content_ir.get("body_blocks", []),
            assets=adapted_content_ir.get("assets", []),
            content_type=adapted_content_ir.get("content_type", "article"),
        )
        platform_copies = self.platform_stylist.generate(adapted_analysis, platforms=request.platforms)

        adapters = select_adapters(request.platforms)
        platforms = list(adapters.keys())

        # 尝试为每个平台调用 LLM 生成专属文案
        llm_platform_results: dict[str, dict[str, Any] | None] = {}
        for p in platforms:
            platform_style = PLATFORM_STYLES.get(p, {})
            llm_result = self._try_platform_llm_rewrite(request, p, platform_style, adapted_content_ir)
            llm_platform_results[p] = llm_result

        drafts = call_tool(
            "platform.render",
            "改写后的统一内容 IR 和目标平台列表。",
            lambda: self._render_platform_drafts(
                adapted_content_ir,
                adapters,
                platform_copies,
                llm_platform_results,
                request,
            ),
        )
        validation_report = call_tool(
            "platform.validate",
            "多平台草稿和平台 profile 限制。",
            lambda: {
                platform: adapters[platform].validate(draft)
                + self.preview_service._validate_media_for_platform(platform, draft)
                for platform, draft in drafts.items()
            },
        )
        compliance_payload = call_tool(
            "compliance.review",
            "统一内容 IR、平台草稿和校验报告。",
            lambda: self._review_compliance(adapted_content_ir, validation_report),
        )

        preview_id: str | None = request.preview_id or str(uuid4())

        # 计算 LLM 状态
        if not self.settings.openai_api_key or request.use_llm == "disabled":
            llm_status = "disabled"
        elif self._llm_tracker.succeeded:
            llm_status = "available"
        elif self._llm_tracker.attempted:
            llm_status = "degraded"
        else:
            llm_status = "disabled"

        response = AgentAdaptPreviewResponse(
            run_id=run_id,
            status="succeeded",
            preview_id=preview_id,
            tool_calls=tool_calls,
            metadata=metadata,
            rewritten_content=rewritten_content,
            content_ir=adapted_content_ir,
            drafts=drafts,
            validation_report=validation_report,
            compliance_report=compliance_payload["compliance_report"],
            recommendations=compliance_payload["recommendations"],
            created_at=created_at,
            llm_status=llm_status,
        )
        record = AgentRunRecord(
            id=run_id,
            status=response.status,
            workflow="adapt_preview",
            preview_id=preview_id,
            platforms=platforms,
            request_payload=request.model_dump(mode="json"),
            tool_calls=[call.model_dump(mode="json") for call in tool_calls],
            result_payload=response.model_dump(mode="json"),
        )
        self.session.add(record)
        await self.session.commit()
        return response

    def _extract_metadata(
        self,
        request: AgentAdaptPreviewRequest,
        analysis,
    ) -> AgentGeneratedMetadata:
        rule_metadata = self._rule_metadata(request, analysis)

        # 尝试 LLM 生成更精准的标题/关键词/摘要
        existing_title = self._clean_title(request.title)
        existing_tags = self._clean_tags(request.tags)
        can_update_title = self._should_update_title(request) or not existing_title
        can_update_tags = self._should_update_tags(request) or not existing_tags
        if request.use_llm != "disabled" and self.settings.openai_api_key:
            llm_payload = self._try_llm_json(
                request,
                purpose="extract_metadata",
                prompt=self._metadata_prompt(rule_metadata),
            )
            if llm_payload:
                llm_title = self._clean_title(llm_payload.get("title"))
                llm_tags = self._clean_tags(llm_payload.get("tags"))
                llm_summary = self._clean_summary(llm_payload.get("summary"))
                if llm_title and can_update_title:
                    rule_metadata["title"] = llm_title
                if llm_tags and can_update_tags:
                    rule_metadata["tags"] = llm_tags
                if llm_summary:
                    rule_metadata["summary"] = llm_summary
                rule_metadata["source"] = "llm"

        return AgentGeneratedMetadata(**rule_metadata)

    def _rewrite_content(
        self,
        request: AgentAdaptPreviewRequest,
        metadata: AgentGeneratedMetadata,
    ) -> AgentRewrittenContent:
        normalized_body = self._normalize_user_body(request.body)
        rule_body = self._rule_rewrite_body(normalized_body, request.style_goal, request.rewrite_strength)
        source = "rule"
        llm_payload = self._try_llm_json(
            request,
            purpose="adapt_preview",
            prompt=self._rewrite_prompt(metadata),
        )
        if llm_payload is not None:
            llm_title = self._clean_title(llm_payload.get("title"))
            llm_summary = self._clean_summary(llm_payload.get("summary"))
            llm_tags = self._clean_tags(llm_payload.get("tags"))
            existing_title = self._clean_title(request.title)
            existing_tags = self._clean_tags(request.tags)
            can_update_title = self._should_update_title(request) or not existing_title
            can_update_tags = self._should_update_tags(request) or not existing_tags
            if llm_title and can_update_title:
                metadata.title = llm_title
            if llm_summary:
                metadata.summary = llm_summary
            if llm_tags and can_update_tags:
                metadata.tags = llm_tags
            if isinstance(llm_payload.get("body"), str):
                rule_body = llm_payload["body"].strip() or rule_body
            source = "llm"
            metadata.source = "llm"

        rule_body = self._postprocess_rewritten_body(rule_body)
        return AgentRewrittenContent(
            title=self._clean_title(metadata.title) or "内容发布草稿",
            body=rule_body,
            tags=metadata.tags,
            style_goal=request.style_goal,
            rewrite_strength=request.rewrite_strength,
            source=source,
        )

    @staticmethod
    def _render_platform_drafts(
        content_ir: dict[str, Any],
        adapters: dict[str, Any],
        platform_copies: dict[str, Any],
        llm_platform_results: dict[str, dict[str, Any] | None] | None = None,
        request: AgentAdaptPreviewRequest | None = None,
    ) -> dict[str, dict[str, Any]]:
        drafts: dict[str, dict[str, Any]] = {}
        can_update_title = (
            True
            if request is None
            else ToolDrivenAgentOrchestrator._should_update_title(request)
        )
        can_update_tags = (
            True
            if request is None
            else ToolDrivenAgentOrchestrator._should_update_tags(request)
        )
        for platform, adapter in adapters.items():
            copy = platform_copies.get(platform)
            platform_content_ir = dict(content_ir)

            # 优先使用 LLM 生成的平台专属文案
            llm_result = (llm_platform_results or {}).get(platform)
            if llm_result:
                platform_body = ToolDrivenAgentOrchestrator._postprocess_rewritten_body(
                    llm_result.get("body", "")
                )
                platform_title = ToolDrivenAgentOrchestrator._clean_title(llm_result.get("title"))
                platform_summary = ToolDrivenAgentOrchestrator._clean_summary(llm_result.get("summary"))
                platform_tags = ToolDrivenAgentOrchestrator._clean_tags(llm_result.get("tags"))
                if platform_title and (
                    can_update_title
                    or not ToolDrivenAgentOrchestrator._clean_title(platform_content_ir.get("title"))
                ):
                    platform_content_ir["title"] = platform_title
                if platform_body:
                    platform_content_ir["body"] = platform_body
                if platform_summary:
                    platform_content_ir["summary"] = platform_summary
                if platform_tags and (
                    can_update_tags
                    or not ToolDrivenAgentOrchestrator._clean_tags(platform_content_ir.get("tags", []))
                ):
                    platform_content_ir["tags"] = platform_tags
            elif copy is not None:
                platform_body = ToolDrivenAgentOrchestrator._postprocess_rewritten_body(copy.plain_body)
                platform_title = ToolDrivenAgentOrchestrator._clean_title(copy.title) or content_ir.get("title", "")
                platform_summary = ToolDrivenAgentOrchestrator._clean_summary(
                    copy.subtitle or content_ir.get("summary", "")
                )
                platform_tags = ToolDrivenAgentOrchestrator._clean_tags(copy.tags or content_ir.get("tags", []))
                platform_content_ir["body"] = platform_body
                platform_content_ir["summary"] = platform_summary
                if platform_title and (
                    can_update_title
                    or not ToolDrivenAgentOrchestrator._clean_title(platform_content_ir.get("title"))
                ):
                    platform_content_ir["title"] = platform_title
                if platform_tags and (
                    can_update_tags
                    or not ToolDrivenAgentOrchestrator._clean_tags(platform_content_ir.get("tags", []))
                ):
                    platform_content_ir["tags"] = platform_tags
            draft = adapter.render(platform_content_ir)
            # 无论是 LLM 还是规则生成的文案，都用最终结果覆盖 adapter 的输出
            draft["title"] = platform_content_ir["title"]
            draft["body"] = platform_content_ir["body"]
            draft["summary"] = platform_content_ir["summary"]
            draft["tags"] = platform_content_ir["tags"]
            if copy is not None and not llm_result:
                draft["structured_sections"] = copy.sections
                draft["platform_copy"] = platform_content_ir["body"]
                draft["media_recommendations"] = copy.media_recommendations
                draft["style_notes"] = copy.style_notes
            drafts[platform] = draft
        return drafts

    @staticmethod
    def _review_compliance(
        content_ir: dict[str, Any],
        validation_report: dict[str, list[dict[str, Any]]],
    ) -> dict[str, Any]:
        compliance_report = SimulatedAgentOrchestrator._review_compliance(content_ir, validation_report)
        recommendations = SimulatedAgentOrchestrator._build_recommendations(
            validation_report,
            compliance_report,
        )
        return {
            "compliance_report": compliance_report,
            "recommendations": recommendations,
        }

    def _rule_metadata(self, request: AgentAdaptPreviewRequest, analysis) -> dict[str, Any]:
        existing_title = self._clean_title(request.title)
        existing_tags = self._clean_tags(request.tags)
        should_keep_title = existing_title and not self._should_update_title(request)
        should_keep_tags = existing_tags and not self._should_update_tags(request)
        title = existing_title if should_keep_title else self._build_title(analysis)
        tags = existing_tags if should_keep_tags else self._build_tags(analysis)
        return {
            "title": self._clean_title(title) or "内容发布草稿",
            "tags": tags,
            "summary": self._clean_summary(analysis.summary),
            "source": "rule",
        }

    @staticmethod
    def _should_update_title(request: AgentAdaptPreviewRequest) -> bool:
        return request.update_title or request.overwrite_existing_metadata

    @staticmethod
    def _should_update_tags(request: AgentAdaptPreviewRequest) -> bool:
        return request.update_tags or request.overwrite_existing_metadata

    @staticmethod
    def _build_title(analysis) -> str:
        candidates = [
            analysis.title,
            analysis.subtitle,
            analysis.chapters[0].title if analysis.chapters else None,
            analysis.summary,
        ]
        for candidate in candidates:
            value = ToolDrivenAgentOrchestrator._clean_title(candidate)
            if value and value.lower() != "untitled content":
                return value
        return "内容发布草稿"

    def _build_tags(self, analysis) -> list[str]:
        candidates: list[str] = []
        candidates.extend(analysis.tags or [])
        candidates.extend(ch.title for ch in analysis.flat_chapters)
        candidates.extend(self._keyword_candidates(analysis.summary))
        candidates.extend(self._keyword_candidates(" ".join(ch.content[:80] for ch in analysis.flat_chapters[:4])))
        return self._clean_tags(candidates) or ["内容运营", "创作发布"]

    @staticmethod
    def _keyword_candidates(text: str) -> list[str]:
        stopwords = {
            "一个",
            "我们",
            "你们",
            "他们",
            "这个",
            "那个",
            "以及",
            "可以",
            "需要",
            "通过",
            "进行",
            "如果",
            "the",
            "and",
            "with",
            "for",
        }
        words = re.findall(r"[A-Za-z][A-Za-z0-9_+-]{2,}|[\u4e00-\u9fff]{2,6}", text)
        return [word for word in words if word.lower() not in stopwords]

    @staticmethod
    def _clean_tags(tags: Any) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        if tags is None:
            return cleaned
        if isinstance(tags, str):
            raw_items: list[Any] = re.split(r"[,，、;；\s]+", tags)
        elif isinstance(tags, list | tuple | set):
            raw_items = list(tags)
        else:
            raw_items = [tags]
        for raw in raw_items:
            tag = ToolDrivenAgentOrchestrator._strip_label_prefix(str(raw)).strip().lstrip("#")
            tag = re.sub(r"^[#＃]+", "", tag).strip()
            key = tag.casefold()
            if tag and key not in seen and tag not in {"题目", "标题", "标签", "关键词", "内容", "正文"}:
                cleaned.append(tag)
                seen.add(key)
        return cleaned

    @staticmethod
    def _rule_rewrite_body(body: str, style_goal: str, strength: str) -> str:
        body = ToolDrivenAgentOrchestrator._normalize_user_body(body)
        if style_goal == "original" or strength == "light":
            return body

        paragraphs = [part.strip() for part in re.split(r"\n{2,}", body) if part.strip()]
        if style_goal == "video":
            heading_blocks = ToolDrivenAgentOrchestrator._extract_heading_blocks(paragraphs)
            if heading_blocks:
                points = "\n".join(f"- {heading}" for heading in heading_blocks[:8])
            else:
                points = "\n".join(f"- {p[:80]}" for p in paragraphs[:6])
            return f"{paragraphs[0] if paragraphs else body}\n\n内容要点\n{points}\n\n欢迎在评论区交流你的看法。"
        if style_goal == "social":
            if not paragraphs:
                return body
            short_parts = "\n\n".join(f"✨ {p}" for p in paragraphs)
            return f"{short_parts}\n\n觉得有用欢迎收藏，也可以留言聊聊你的经验。"
        if style_goal == "knowledge":
            heading_blocks = ToolDrivenAgentOrchestrator._extract_heading_blocks(paragraphs)
            if heading_blocks:
                intro = paragraphs[0] if paragraphs else ""
                return f"{intro}\n\n结构梳理\n\n" + "\n".join(f"{index}. {heading}" for index, heading in enumerate(heading_blocks[:8], start=1))
            return body

        return body

    @staticmethod
    def _normalize_user_body(body: str) -> str:
        lines = [line.rstrip() for line in body.strip().splitlines()]
        normalized: list[str] = []
        skip_labels = {"题目", "标题", "标签", "关键词", "内容", "正文", "导语", "结语"}
        for line in lines:
            stripped = line.strip()
            label_match = ToolDrivenAgentOrchestrator._match_label_line(stripped)
            if label_match:
                value = label_match.group(2).strip()
                if label_match.group(1) in {"内容", "正文"} and not value:
                    continue
                if label_match.group(1) in {"题目", "标题", "标签", "关键词"}:
                    continue
                stripped = value
            stripped = ToolDrivenAgentOrchestrator._strip_label_prefix(stripped)
            if stripped in skip_labels:
                continue
            normalized.append(stripped if stripped else "")
        text = "\n".join(normalized).strip()
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    @staticmethod
    def _extract_heading_blocks(paragraphs: list[str]) -> list[str]:
        headings: list[str] = []
        for paragraph in paragraphs:
            first_line = paragraph.splitlines()[0].strip()
            heading = first_line.lstrip("#").strip()
            if re.match(r"^([一二三四五六七八九十]+、|第[一二三四五六七八九十\d]+[章节]|[0-9]+[.、])", heading):
                headings.append(heading[:60])
            elif first_line.startswith("#"):
                headings.append(heading[:60])
        return headings

    @staticmethod
    def _postprocess_rewritten_body(body: str) -> str:
        text = ToolDrivenAgentOrchestrator._normalize_user_body(body)
        lines = text.splitlines()
        cleaned: list[str] = []
        seen_recent_blocks: set[str] = set()
        structural_headings_seen: set[str] = set()
        previous_non_empty = ""
        boilerplate = "以上内容可作为发布前的结构化草稿，建议结合平台规则继续微调。"

        for line in lines:
            stripped = line.strip()
            if stripped == boilerplate:
                continue
            if ToolDrivenAgentOrchestrator._match_label_line(stripped):
                continue
            if stripped in {"导语", "正文", "结语"}:
                if stripped in structural_headings_seen:
                    continue
                structural_headings_seen.add(stripped)
            if stripped in {"导语", "正文", "结语", "总结"} and stripped == previous_non_empty:
                continue
            if stripped:
                normalized_key = re.sub(r"\s+", "", stripped)
                if len(normalized_key) > 20 and normalized_key in seen_recent_blocks:
                    continue
                seen_recent_blocks.add(normalized_key)
                if len(seen_recent_blocks) > 80:
                    seen_recent_blocks = set(list(seen_recent_blocks)[-40:])
                previous_non_empty = stripped
            cleaned.append(line.rstrip())

        text = "\n".join(cleaned).strip()
        text = re.sub(r"(?:\n{2,}(导语|正文|结语|总结)\n{2,}){2,}", r"\n\n\1\n\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text

    @staticmethod
    def _rewrite_prompt(metadata: AgentGeneratedMetadata) -> str:
        return (
            "你是一个严谨的中文内容编辑。请把用户内容整理成可直接发布的中文正文，并补全标题、摘要和关键词。\n"
            "硬性要求：\n"
            "1. 只返回 JSON：{\"title\": string, \"summary\": string, \"tags\": string[], \"body\": string}，不要返回 Markdown 代码块。\n"
            "2. title 必须是纯标题，不得包含“题目：”“标题：”等前缀。\n"
            "3. tags 只能是关键词数组，不得包含“标签：”“关键词：”等前缀。\n"
            "4. body 只能包含正文内容，不要包含“题目：”“标题：”“标签：”“关键词：”“内容：”“正文：”这些包装字段。\n"
            "5. 不要机械添加“导语/正文/结语”三段式标题；除非原文已有自然的小标题，否则保持原有章节结构。\n"
            "6. 不得重复任何段落、标题或结尾话术；不得连续出现相同小标题。\n"
            "7. 保留原文事实、专有名词、Markdown 标题层级、列表结构和素材占位符。\n"
            "8. 若原文已经较完整，只做润色、去重、结构整理，不要重新包裹一层模板。\n"
            "9. summary 用一句话概括正文，不要复述标题字段。\n"
            "10. 绝对不能偏离原文的主题和核心内容，不要添加原文没有的事实或观点。\n"
            "11. 不得用 ... 或 … 表示硬截断，标题、关键词和正文必须保留完整可读内容。\n"
            f"建议标题：{metadata.title}\n"
            f"建议关键词：{', '.join(metadata.tags)}"
        )

    @staticmethod
    def _metadata_prompt(rule_metadata: dict[str, Any]) -> str:
        return (
            "你是一个专业的中文内容编辑。请根据用户内容，生成精准的标题、关键词和摘要。\n"
            "硬性要求：\n"
            "1. 只返回 JSON：{\"title\": string, \"summary\": string, \"tags\": string[]}，不要返回 Markdown 代码块。\n"
            "2. title 必须是纯标题，不得包含\"题目：\"\"标题：\"等包装字段。\n"
            "3. tags 返回 3-5 个关键词，不得包含\"标签：\"\"关键词：\"等包装字段。\n"
            "4. summary 用 1-2 句话概括正文核心观点。\n"
            "5. 保留原文的专有名词、技术术语，不要编造不存在的信息。\n"
            "6. 标题和摘要必须忠实于原文内容，不要偏离主题。\n"
            f"规则引擎参考标题：{rule_metadata.get('title', '')}\n"
            f"规则引擎参考关键词：{', '.join(rule_metadata.get('tags', []))}\n"
            f"规则引擎参考摘要：{rule_metadata.get('summary', '')}"
        )

    @staticmethod
    def _platform_rewrite_prompt(
        platform: str,
        platform_style: dict[str, Any],
        content_ir: dict[str, Any],
    ) -> str:
        display_name = platform_style.get("display_name", platform)
        tone = platform_style.get("tone", "通用")
        structure_hint = platform_style.get("structure_hint", "")

        # 平台专属风格指导
        platform_guidance = {
            "wechat": (
                "微信公众号平台风格指导：\n"
                "- 尽量保留原文的写作风格和整体结构，不要随意改变作者的表达方式。\n"
                "- 适合长文深度阅读，正文结构清晰，层次分明。\n"
                "- 导语简短有力，能吸引读者继续阅读。\n"
                "- 结尾可适当加入引导关注或互动话术，但不要喧宾夺主。\n"
                "- 语言正式但不死板，保持专业调性。"
            ),
            "zhihu": (
                "知乎平台风格指导：\n"
                "- 保持专业严谨的表达方式，逻辑严密，论证充分。\n"
                "- 适合知识分享和深度讨论，内容要有实质性见解。\n"
                "- 开头可抛出一个引人思考的问题或观点。\n"
                "- 使用分点或列表增强可读性，引用数据增强说服力。\n"
                "- 结尾给出明确结论或行动建议，体现思考深度。"
            ),
            "xiaohongshu": (
                "小红书平台风格指导：\n"
                "- 采用谈心式、亲切真诚的表达方式，像和好朋友分享经验。\n"
                "- 用第一人称写作，拉近与读者的距离。\n"
                "- 语言轻松自然，可以适当使用表情符号和网络用语。\n"
                "- 突出内容的实用价值和亮点，让读者觉得「学到了」。\n"
                "- 不要为了短标题或短笔记硬截断内容；不得用 ... 或 … 表示省略。\n"
                "- 结尾可引导点赞、收藏、评论等互动。"
            ),
            "bilibili": (
                "B站平台风格指导：\n"
                "- 采用轻松活泼、年轻化的表达方式，有网感但不低俗。\n"
                "- 适合视频简介，语言简洁有趣。\n"
                "- 可使用年轻人常用的表达方式，适当玩梗。\n"
                "- 内容要点用分点列出，清晰易懂。\n"
                "- 结尾可引导一键三连、弹幕互动等。"
            ),
        }.get(platform, f"通用风格指导：{tone}\n推荐结构：{structure_hint}")

        return (
            f"你是{display_name}平台的专业内容创作者。请把以下内容改写为适合{display_name}发布的版本。\n\n"
            f"【核心原则 - 必须遵守】\n"
            f"1. 绝对不能偏离输入内容的主题和核心信息，不要添加原文没有的事实或观点。\n"
            f"2. 保留原文的所有关键事实、专有名词、数据和结论。\n"
            f"3. 只做表达方式的适配和优化，不做内容的曲解或篡改。\n\n"
            f"{platform_guidance}\n\n"
            "硬性要求：\n"
            "1. 只返回 JSON：{\"title\": string, \"summary\": string, \"tags\": string[], \"body\": string}，不要返回 Markdown 代码块。\n"
            "2. title 必须符合该平台标题风格，不得包含\"题目：\"\"标题：\"等前缀。\n"
            "3. tags 必须是关键词数组，不得包含\"标签：\"\"关键词：\"等前缀。\n"
            "4. body 只能包含正文内容，不要包含\"题目：\"\"标题：\"\"标签：\"\"内容：\"\"正文：\"这些包装字段。\n"
            "5. 根据平台风格指导调整内容表达方式，但不要改变核心信息。\n"
            "6. 保留原文的事实、专有名词和素材占位符（如【图片：xxx】）。\n"
            "7. summary 用一句话概括改写后的正文核心观点。\n"
            f"当前标题：{content_ir.get('title', '')}\n"
            f"当前关键词：{', '.join(content_ir.get('tags', []))}"
        )

    @staticmethod
    def _match_label_line(text: str) -> re.Match[str] | None:
        return re.match(
            r"^(?:[#>*\-\s]*)?(题目|标题|标签|关键词|内容|正文)\s*[：:]\s*(.*)$",
            text.strip().strip("*_"),
        )

    @staticmethod
    def _strip_label_prefix(value: Any) -> str:
        text = str(value or "").strip().lstrip("#").strip()
        text = text.strip("*_` ")
        while True:
            label_match = ToolDrivenAgentOrchestrator._match_label_line(text)
            if not label_match:
                break
            next_value = label_match.group(2).strip()
            if next_value:
                text = next_value.strip("*_` ")
                continue
            return ""
        return text

    @staticmethod
    def _clean_title(value: Any) -> str:
        title = ToolDrivenAgentOrchestrator._strip_label_prefix(value)
        title = re.sub(r"\s+", " ", title).strip(" ：:")
        return title

    @staticmethod
    def _clean_summary(value: Any) -> str:
        summary = ToolDrivenAgentOrchestrator._strip_label_prefix(value)
        summary = re.sub(r"\s+", " ", summary).strip()
        return summary

    def _try_llm_json(
        self,
        request: AgentAdaptPreviewRequest,
        purpose: str,
        prompt: str,
    ) -> dict[str, Any] | None:
        if request.use_llm == "disabled":
            return None
        if not self.settings.openai_api_key:
            return None

        self._llm_tracker.on_attempt()

        payload = {
            "model": self.settings.openai_model,
            "messages": [
                {
                    "role": "system",
                    "content": prompt,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "purpose": purpose,
                            "title": request.title,
                            "body": request.body,
                            "tags": request.tags,
                            "style_goal": request.style_goal,
                            "rewrite_strength": request.rewrite_strength,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            "max_tokens": 4096,
            # DeepSeek 不支持 response_format，去掉避免影响
        }
        try:
            endpoint = f"{self.settings.openai_base_url.rstrip('/')}/chat/completions"
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {self.settings.openai_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
            response.raise_for_status()
            text = self._extract_chat_completion_text(response.json())
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                self._llm_tracker.on_success()
                return parsed
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "LLM request failed [purpose=%s] HTTP %s: %s  model=%s endpoint=%s",
                purpose,
                exc.response.status_code,
                exc.response.text[:200],
                self.settings.openai_model,
                self.settings.openai_base_url,
            )
            return None
        except httpx.TimeoutException:
            logger.warning(
                "LLM request timed out [purpose=%s]  model=%s endpoint=%s",
                purpose,
                self.settings.openai_model,
                self.settings.openai_base_url,
            )
            return None
        except json.JSONDecodeError as exc:
            logger.warning(
                "LLM response was not valid JSON [purpose=%s]: %s  model=%s",
                purpose,
                exc,
                self.settings.openai_model,
            )
            return None
        except Exception as exc:
            logger.warning(
                "LLM request unexpected error [purpose=%s]: %s: %s  model=%s endpoint=%s",
                purpose,
                type(exc).__name__,
                exc,
                self.settings.openai_model,
                self.settings.openai_base_url,
            )
            return None

    def _try_platform_llm_rewrite(
        self,
        request: AgentAdaptPreviewRequest,
        platform: str,
        platform_style: dict[str, Any],
        content_ir: dict[str, Any],
    ) -> dict[str, Any] | None:
        """尝试为单个平台调用 LLM 生成专属文案。"""
        return self._try_llm_json(
            request,
            purpose=f"platform_rewrite.{platform}",
            prompt=self._platform_rewrite_prompt(platform, platform_style, content_ir),
        )

    @staticmethod
    def _extract_chat_completion_text(payload: dict[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return ""
        message = choices[0].get("message", {})
        content = message.get("content", "")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks = [
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            ]
            return "\n".join(chunks)
        return ""

    @staticmethod
    def _jsonable(value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            dumped = value.model_dump(mode="json")
            return dumped if isinstance(dumped, dict) else {"value": dumped}
        if isinstance(value, dict):
            return json.loads(json.dumps(value, ensure_ascii=False, default=str))
        return {"value": json.loads(json.dumps(value, ensure_ascii=False, default=str))}
