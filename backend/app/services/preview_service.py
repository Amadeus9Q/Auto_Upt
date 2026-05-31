from __future__ import annotations

from datetime import UTC, datetime
import json
import logging
import re
from typing import Any
from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.registry import select_adapters
from backend.app.agents.content_analyst import ContentAnalystAgent
from backend.app.agents.platform_stylist import PlatformStylistAgent
from backend.app.core.config import get_settings
from backend.app.models.content import PreviewRecord
from backend.app.schemas.content import (
    AdaptContentRequest,
    ContentInput,
    PreviewCreateRequest,
    PreviewDraftUpdateRequest,
    PreviewResponse,
)

logger = logging.getLogger(__name__)


class PreviewService:
    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.content_analyst = ContentAnalystAgent()
        self.platform_stylist = PlatformStylistAgent()

    def normalize_content(self, request: ContentInput) -> dict[str, Any]:
        body = request.body.strip()
        title = self._normalize_title(request.title, body)
        tags = self._normalize_tags(request.tags)

        # ---- 标题或关键词缺失时，自动调用 LLM 生成 ----
        title_missing = not title or title == "Untitled Content"
        tags_missing = not tags
        if body and (title_missing or tags_missing):
            if title_missing:
                title_prompt = (
                    "你是一个专业的中文内容编辑。请根据正文内容生成一个精炼的标题。\n"
                    "硬性要求：\n"
                    "1. 只返回 JSON：{\"title\": string}，不要返回 Markdown 代码块。\n"
                    "2. title 必须是纯标题，不得包含\"题目：\"\"标题：\"等前缀。\n"
                    "3. 标题必须忠实于原文内容，不要偏离主题。\n"
                    f"正文：\n{body[:3000]}"
                )
                llm_title, _ = self._call_llm_for_metadata(title_prompt)
                if llm_title:
                    title = llm_title
            if tags_missing:
                tags_prompt = (
                    "你是一个专业的中文内容编辑。请根据正文内容提取5个以内的关键词。\n"
                    "硬性要求：\n"
                    "1. 只返回 JSON：{\"tags\": string[]}，不要返回 Markdown 代码块。\n"
                    "2. tags 必须是纯关键词数组，每个关键词简短精炼。\n"
                    "3. 不得包含\"标签：\"\"关键词：\"等前缀。\n"
                    f"标题：{title}\n正文：\n{body[:3000]}"
                )
                _, llm_tags = self._call_llm_for_metadata(tags_prompt)
                if llm_tags:
                    tags = llm_tags
        summary = self._summarize(body)
        assets = [asset.model_dump() for asset in request.assets]
        body_blocks = self._normalize_blocks(body, assets, [block.model_dump() for block in request.content_blocks])

        # ---- 深度内容分析：章节划分 + 媒体识别 ----
        analysis = self.content_analyst.analyze(
            body=body,
            title=title,
            tags=tags,
            content_blocks=body_blocks,
            assets=assets,
            content_type=request.content_type,
        )

        return {
            "id": str(uuid4()),
            "title": title,
            "body": body,
            "summary": summary,
            "subtitle": analysis.subtitle,
            "content_type": request.content_type,
            "tags": tags,
            "assets": assets,
            "body_blocks": body_blocks,
            "media_slots": self._build_media_slots(assets, body_blocks, request.cover_asset_id),
            "cover_asset_id": request.cover_asset_id,
            "word_count": self._count_words(body),
            # 新增：章节和媒体分析结果
            "chapters": [ch.model_dump() for ch in analysis.chapters],
            "flat_chapters": [ch.model_dump() for ch in analysis.flat_chapters],
            "all_media": [m.model_dump() for m in analysis.all_media],
            "media_by_kind": {
                k: [m.model_dump() for m in v]
                for k, v in analysis.media_by_kind.items()
            },
            "created_at": datetime.now(UTC).isoformat(),
        }

    def adapt_content(
        self,
        request: AdaptContentRequest | PreviewCreateRequest,
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        content_ir = self.normalize_content(request)
        adapters = select_adapters(request.platforms)
        drafts: dict[str, dict[str, Any]] = {}
        validation_report: dict[str, list[dict[str, Any]]] = {}

        for platform, adapter in adapters.items():
            draft = adapter.render(content_ir)
            drafts[platform] = draft
            validation_report[platform] = adapter.validate(draft) + self._validate_media_for_platform(platform, draft)

        return content_ir, drafts, validation_report

    def create_preview_in_memory(self, request: PreviewCreateRequest) -> PreviewResponse:
        """生成预览数据但不写入数据库，纯内存计算。"""
        content_ir, drafts, validation_report = self.adapt_content(request)
        return PreviewResponse(
            preview_id=str(uuid4()),
            content_ir=content_ir,
            drafts=drafts,
            validation_report=validation_report,
            created_at=datetime.now(UTC),
        )

    async def create_preview(self, request: PreviewCreateRequest) -> PreviewRecord:
        if self.session is None:
            raise RuntimeError("PreviewService.create_preview requires a database session.")

        content_ir, drafts, validation_report = self.adapt_content(request)
        record = PreviewRecord(
            title=content_ir["title"],
            body=content_ir["body"],
            content_type=content_ir["content_type"],
            raw_input=request.model_dump(),
            content_ir=content_ir,
            drafts=drafts,
            validation_report=validation_report,
        )
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def get_preview(self, preview_id: str) -> PreviewRecord | None:
        if self.session is None:
            raise RuntimeError("PreviewService.get_preview requires a database session.")
        return await self.session.get(PreviewRecord, preview_id)

    def update_preview_draft_in_memory(
        self,
        draft: dict[str, Any],
        platform: str,
        request: PreviewDraftUpdateRequest,
    ) -> dict[str, list[dict[str, Any]]]:
        """对平台草稿执行校验，不写数据库。返回该平台的校验报告。"""
        adapters = select_adapters([platform])
        adapter = adapters[platform]
        updated_draft = dict(draft or {})
        payload = request.model_dump(exclude_unset=True)

        if "title" in payload and payload["title"] is not None:
            updated_draft["title"] = payload["title"].strip()
        if "body" in payload and payload["body"] is not None:
            updated_draft["body"] = payload["body"]
        if "summary" in payload and payload["summary"] is not None:
            updated_draft["summary"] = payload["summary"].strip()
        if "tags" in payload and payload["tags"] is not None:
            updated_draft["tags"] = self._normalize_tags(payload["tags"])

        return adapter.validate(updated_draft) + self._validate_media_for_platform(platform, updated_draft)

    async def update_preview_draft(
        self,
        preview_id: str,
        platform: str,
        request: PreviewDraftUpdateRequest,
    ) -> PreviewRecord | None:
        if self.session is None:
            raise RuntimeError("PreviewService.update_preview_draft requires a database session.")

        record = await self.session.get(PreviewRecord, preview_id)
        if record is None:
            return None

        drafts = dict(record.drafts or {})
        if platform not in drafts:
            raise LookupError(f"Draft for platform {platform} not found.")

        adapters = select_adapters([platform])
        adapter = adapters[platform]
        draft = dict(drafts[platform] or {})
        payload = request.model_dump(exclude_unset=True)

        if "title" in payload and payload["title"] is not None:
            draft["title"] = payload["title"].strip()
        if "body" in payload and payload["body"] is not None:
            draft["body"] = payload["body"]
        if "summary" in payload and payload["summary"] is not None:
            draft["summary"] = payload["summary"].strip()
        if "tags" in payload and payload["tags"] is not None:
            draft["tags"] = self._normalize_tags(payload["tags"])

        drafts[platform] = draft
        validation_report = dict(record.validation_report or {})
        validation_report[platform] = adapter.validate(draft) + self._validate_media_for_platform(platform, draft)

        record.drafts = drafts
        record.validation_report = validation_report
        await self.session.commit()
        await self.session.refresh(record)
        return record

    @staticmethod
    def to_response(record: PreviewRecord) -> PreviewResponse:
        return PreviewResponse(
            preview_id=record.id,
            content_ir=record.content_ir,
            drafts=record.drafts,
            validation_report=record.validation_report,
            created_at=record.created_at,
        )

    @staticmethod
    def _normalize_title(title: str | None, body: str) -> str:
        if title and title.strip():
            return PreviewService._clean_generated_title(title.strip())
        for line in body.splitlines():
            candidate = line.strip().lstrip("#").strip()
            if candidate:
                return PreviewService._clean_generated_title(candidate[:80])
        return "Untitled Content"

    @staticmethod
    def _normalize_tags(tags: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for tag in tags:
            value = tag.strip().lstrip("#")
            # 去除中文序号前缀（一、二、三 等）和阿拉伯数字前缀（1. 2. 等）
            value = re.sub(r"^[一二三四五六七八九十]+[、.．]\s*", "", value)
            value = re.sub(r"^\d+[、.．]\s*", "", value)
            key = value.casefold()
            if value and key not in seen:
                normalized.append(value)
                seen.add(key)
        return normalized

    @staticmethod
    def _call_llm_for_metadata(prompt: str) -> tuple[str, list[str]]:
        """
        调用 LLM 生成标题或关键词。返回 (title, tags)。
        """
        settings = get_settings()
        if not settings.openai_api_key:
            logger.info("LLM API key not configured, skipping metadata generation")
            return ("", [])

        try:
            response = httpx.post(
                url=f"{settings.openai_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.openai_model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.7,
                    "max_tokens": 500,
                },
                timeout=httpx.Timeout(30),
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]

            # 清理 Markdown 代码块
            content = content.strip()
            if content.startswith("```"):
                content = re.sub(r"^```(?:json)?\s*", "", content)
                content = re.sub(r"\s*```$", "", content)

            result = json.loads(content)
            title = PreviewService._clean_generated_title(result.get("title", ""))
            tags = PreviewService._clean_generated_tags(result.get("tags", []))
            logger.info(f"LLM generated title: {title}, tags: {tags}")
            return (title, tags if isinstance(tags, list) else [])
        except Exception as exc:
            logger.warning(f"LLM metadata generation failed, using fallback: {exc}")
            return ("", [])

    @staticmethod
    def _clean_generated_title(raw: str) -> str:
        """去掉 LLM 可能加上的 题目：/标题：/如何看待： 等前缀"""
        if not raw:
            return ""
        return re.sub(
            r"^\s*(题目|标题|如何看待|Title)\s*[：:]\s*",
            "",
            raw.strip(),
        ).strip()

    @staticmethod
    def _clean_generated_tags(raw: Any) -> list[str]:
        """去掉 LLM 可能加上的 标签：/关键词： 等前缀"""
        if not isinstance(raw, list):
            return []
        result: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                continue
            cleaned = re.sub(
                r"^\s*(标签|关键词|Tags|Keywords)\s*[：:]\s*",
                "",
                item.strip(),
            ).strip()
            if cleaned:
                result.append(cleaned)
        return result

    @staticmethod
    def _summarize(body: str) -> str:
        for paragraph in body.splitlines():
            candidate = paragraph.strip().lstrip("#").strip()
            if candidate:
                return candidate[:160]
        return body[:160]

    @staticmethod
    def _count_words(body: str) -> int:
        if any(char.isspace() for char in body):
            return len([part for part in body.split() if part.strip()])
        return len(body)

    @staticmethod
    def _normalize_blocks(body: str, assets: list[dict[str, Any]], blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        asset_map = {asset.get("id"): asset for asset in assets if asset.get("id")}
        normalized: list[dict[str, Any]] = []

        source_blocks = blocks or PreviewService._parse_asset_markers(body)
        for block in source_blocks:
            if block.get("type") == "text":
                text = (block.get("text") or "").strip()
                if text:
                    normalized.append({"type": "text", "text": text})
                continue

            asset_id = block.get("asset_id")
            asset = asset_map.get(asset_id)
            if not asset:
                continue
            kind = block.get("asset_kind") or asset.get("type")
            normalized.append(
                {
                    "type": "asset",
                    "asset_id": asset_id,
                    "asset_kind": kind,
                    "role": block.get("role") or "inline",
                    "asset": asset,
                }
            )

        if not normalized and body:
            normalized.append({"type": "text", "text": body})
        return normalized

    @staticmethod
    def _parse_asset_markers(body: str) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        pattern = re.compile(r"\{\{asset:(image|video|audio):([^}]+)\}\}")
        cursor = 0

        for match in pattern.finditer(body):
            text = body[cursor : match.start()].strip()
            if text:
                blocks.append({"type": "text", "text": text})
            blocks.append({"type": "asset", "asset_kind": match.group(1), "asset_id": match.group(2), "role": "inline"})
            cursor = match.end()

        trailing_text = body[cursor:].strip()
        if trailing_text:
            blocks.append({"type": "text", "text": trailing_text})
        return blocks

    @staticmethod
    def _build_media_slots(
        assets: list[dict[str, Any]],
        body_blocks: list[dict[str, Any]],
        cover_asset_id: str | None,
    ) -> dict[str, Any]:
        asset_map = {asset.get("id"): asset for asset in assets if asset.get("id")}
        cover = asset_map.get(cover_asset_id) if cover_asset_id else None
        if cover is None:
            cover = next((asset for asset in assets if asset.get("usage") == "default_cover"), None)
        if cover is None:
            cover = next((asset for asset in assets if asset.get("type") in ("cover", "image")), None)

        body_assets = [block["asset"] for block in body_blocks if block.get("type") == "asset" and block.get("asset")]
        return {
            "cover": cover,
            "main_video": next((asset for asset in assets if asset.get("usage") == "bilibili_video"), None),
            "body_images": [asset for asset in body_assets if asset.get("type") in ("image", "body_image")],
            "body_videos": [asset for asset in body_assets if asset.get("type") == "video"],
            "body_audios": [asset for asset in body_assets if asset.get("type") == "audio"],
            "unsupported": [],
        }

    @staticmethod
    def _validate_media_for_platform(platform: str, draft: dict[str, Any]) -> list[dict[str, Any]]:
        slots = draft.get("media_slots") or {}
        issues: list[dict[str, Any]] = []

        if platform == "bilibili":
            if not slots.get("main_video"):
                issues.append(
                    {
                        "level": "error",
                        "code": "BILIBILI_VIDEO_REQUIRED",
                        "field": "media_slots.main_video",
                        "message": "B站真实发布需要选择一个视频文件。",
                    }
                )
            if not slots.get("cover"):
                issues.append(
                    {
                        "level": "warning",
                        "code": "BILIBILI_COVER_RECOMMENDED",
                        "field": "media_slots.cover",
                        "message": "建议为 B站稿件选择封面图。",
                    }
                )

        if platform == "wechat":
            if slots.get("body_videos") or slots.get("body_audios"):
                issues.append(
                    {
                        "level": "warning",
                        "code": "WECHAT_INLINE_MEDIA_PLACEHOLDER",
                        "field": "body_blocks",
                        "message": "公众号正文中的视频和音频当前仅作为预览占位，真实上传规则需在后续联调中确认。",
                    }
                )

        if platform in {"zhihu", "xiaohongshu"} and (slots.get("body_videos") or slots.get("body_audios")):
            issues.append(
                {
                    "level": "info",
                    "code": "BROWSER_ASSISTED_MEDIA_PENDING",
                    "field": "body_blocks",
                    "message": "该平台的多媒体真实发布将在第三阶段浏览器辅助发布中接入。",
                }
            )

        return issues
