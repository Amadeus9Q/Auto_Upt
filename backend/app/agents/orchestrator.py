from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.app.adapters.base import PlatformAdapter
from backend.app.adapters.registry import select_adapters
from backend.app.agents.content_analyst import ContentAnalystAgent
from backend.app.agents.platform_stylist import PlatformStylistAgent
from backend.app.schemas.agent import (
    AgentRunRequest,
    AgentRunResponse,
    AgentStep,
    AgentStepStatusLiteral,
)
from backend.app.schemas.analysis import (
    Chapter,
    ContentAnalysis,
    MediaItem,
)
from backend.app.services.preview_service import PreviewService


class SimulatedAgentOrchestrator:
    """Agent 编排器。

    整合内容分析（LLM 章节划分 + 媒体识别）、平台文案生成、
    草稿渲染、格式校验、合规检查和模拟发布的完整工作流。
    """

    def __init__(self) -> None:
        self.preview_service = PreviewService()
        self.content_analyst = ContentAnalystAgent()
        self.platform_stylist = PlatformStylistAgent()

    def run_preview_workflow(self, request: AgentRunRequest) -> AgentRunResponse:
        created_at = datetime.now(UTC)
        run_id = str(uuid4())
        steps: list[AgentStep] = []

        # ---- Step 1: 内容标准化 + 深度分析 (PreviewService) ----
        # normalize_content 内部已调用 ContentAnalystAgent.analyze()，
        # 返回的 content_ir 已包含 chapters, flat_chapters, all_media, media_by_kind
        content_ir = self.preview_service.normalize_content(request)

        # ---- Step 2: 提取分析结果（从 content_ir 中读取，避免重复调用 analyze）----
        analysis = self._analysis_from_ir(content_ir)

        steps.append(
            self._step(
                name="内容分析",
                role="Content Analyst",
                input_summary="原始标题、正文、标签和素材。",
                output={
                    "title": analysis.title,
                    "subtitle": analysis.subtitle,
                    "summary": analysis.summary,
                    "content_type": analysis.content_type,
                    "word_count": analysis.total_word_count,
                    "chapter_count": len(analysis.chapters),
                    "chapters": [
                        {
                            "title": ch.title,
                            "level": ch.level,
                            "word_count": ch.word_count,
                            "media_count": len(ch.media_items),
                            "sub_count": len(ch.sub_chapters),
                        }
                        for ch in analysis.chapters
                    ],
                    "media_summary": {
                        "total": len(analysis.all_media),
                        "images": len(analysis.media_by_kind.get("image", [])),
                        "videos": len(analysis.media_by_kind.get("video", [])),
                        "audios": len(analysis.media_by_kind.get("audio", [])),
                    },
                    "tags": analysis.tags,
                },
            )
        )

        # ---- Step 3: 平台适配器选择 ----
        adapters = select_adapters(request.platforms)
        platforms = list(adapters.keys())

        # ---- Step 4: 平台风格规划 (PlatformStylistAgent) ----
        # 生成结构化的平台文案
        platform_copies = self.platform_stylist.generate(
            analysis=analysis,
            platforms=platforms,
        )

        steps.append(
            self._step(
                name="平台风格规划",
                role="Platform Stylist",
                input_summary="内容分析结果（章节树、媒体列表）和目标平台列表。",
                output={
                    platform: {
                        "display_name": copy.display_name,
                        "title": copy.title,
                        "section_count": len(copy.sections),
                        "tag_count": len(copy.tags),
                        "media_recommendations": len(copy.media_recommendations),
                    }
                    for platform, copy in platform_copies.items()
                },
            )
        )

        # ---- Step 5: Adapter 渲染 (保持兼容) ----
        drafts: dict[str, dict[str, Any]] = {}
        for platform, adapter in adapters.items():
            draft = adapter.render(content_ir)
            # 注入 PlatformStylist 生成的平台文案到 draft 中
            if platform in platform_copies:
                pc = platform_copies[platform]
                draft["structured_sections"] = pc.sections
                draft["platform_copy"] = pc.plain_body
                draft["media_recommendations"] = pc.media_recommendations
                draft["style_notes"] = pc.style_notes
            drafts[platform] = draft

        steps.append(
            self._step(
                name="平台草稿渲染",
                role="Platform Stylist",
                input_summary="统一内容 IR、平台 profile、平台风格规划和结构化文案。",
                output={
                    platform: {
                        "title": draft.get("title"),
                        "body_length": len(draft.get("body", "")),
                        "tag_count": len(draft.get("tags", [])),
                        "has_structured_sections": "structured_sections" in draft,
                    }
                    for platform, draft in drafts.items()
                },
            )
        )

        # ---- Step 6: 格式校验 ----
        validation_report = {
            platform: adapters[platform].validate(draft)
            for platform, draft in drafts.items()
        }
        steps.append(
            self._step(
                name="格式校验",
                role="Format Linter",
                input_summary="平台草稿和平台限制规则。",
                output={
                    platform: self._validation_summary(issues)
                    for platform, issues in validation_report.items()
                },
            )
        )

        # ---- Step 7: 合规检查 ----
        compliance_report = self._review_compliance(content_ir, validation_report)
        steps.append(
            self._step(
                name="合规检查",
                role="Compliance Reviewer",
                input_summary="统一内容 IR、平台草稿和格式校验报告。",
                output=compliance_report,
            )
        )

        # ---- Step 8: 模拟发布 ----
        simulation_results: dict[str, dict[str, Any]] = {}
        if request.include_simulation:
            simulation_results = {
                platform: adapters[platform].simulate(draft)
                for platform, draft in drafts.items()
            }
            steps.append(
                self._step(
                    name="模拟发布",
                    role="Publisher Agent",
                    input_summary="平台草稿和模拟发布模式。",
                    output={
                        platform: {
                            "status": result["status"],
                            "preview_url": result["preview_url"],
                            "screenshot_path": result["screenshot_path"],
                        }
                        for platform, result in simulation_results.items()
                    },
                )
            )
        else:
            steps.append(
                self._step(
                    name="模拟发布",
                    role="Publisher Agent",
                    status="skipped",
                    input_summary="请求关闭 include_simulation。",
                    output={"message": "已跳过模拟发布步骤。"},
                )
            )

        # ---- Step 9: 恢复建议 ----
        recommendations = self._build_recommendations(
            validation_report=validation_report,
            compliance_report=compliance_report,
        )
        steps.append(
            self._step(
                name="失败恢复建议",
                role="Recovery Agent",
                input_summary="格式校验、合规检查和模拟发布结果。",
                output={"recommendations": recommendations},
            )
        )

        return AgentRunResponse(
            run_id=run_id,
            status="succeeded",
            mode="simulate",
            platforms=platforms,
            steps=steps,
            content_ir=content_ir,
            drafts=drafts,
            validation_report=validation_report,
            compliance_report=compliance_report,
            simulation_results=simulation_results,
            recommendations=recommendations,
            created_at=created_at,
        )

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _analysis_from_ir(content_ir: dict[str, Any]) -> ContentAnalysis:
        """从 content_ir（normalize_content 输出）重建 ContentAnalysis 对象。

        normalize_content 已将 analyze() 结果序列化到 content_ir 中，
        此方法反序列化回 Pydantic 模型，供 PlatformStylistAgent 等下游使用。
        避免重复调用 analyze()（尤其是 LLM API 调用）。
        """
        # 重建 chapters
        chapters = [Chapter(**ch) for ch in content_ir.get("chapters", [])]
        flat_chapters = [Chapter(**ch) for ch in content_ir.get("flat_chapters", [])]

        # 重建 all_media
        all_media = [MediaItem(**m) for m in content_ir.get("all_media", [])]

        # 重建 media_by_kind
        media_by_kind: dict[str, list[MediaItem]] = {}
        for kind, items in content_ir.get("media_by_kind", {}).items():
            media_by_kind[kind] = [MediaItem(**m) for m in items]

        return ContentAnalysis(
            title=content_ir.get("title"),
            subtitle=content_ir.get("subtitle"),
            chapters=chapters,
            flat_chapters=flat_chapters,
            all_media=all_media,
            media_by_kind=media_by_kind,
            summary=content_ir.get("summary", ""),
            total_word_count=content_ir.get("word_count", 0),
            tags=content_ir.get("tags", []),
            content_type=content_ir.get("content_type", "article"),
        )

    @staticmethod
    def _step(
        name: str,
        role: str,
        input_summary: str,
        output: dict[str, Any],
        status: AgentStepStatusLiteral = "succeeded",
    ) -> AgentStep:
        started_at = datetime.now(UTC)
        completed_at = datetime.now(UTC)
        return AgentStep(
            name=name,
            role=role,
            status=status,
            input_summary=input_summary,
            output=output,
            started_at=started_at,
            completed_at=completed_at,
        )

    @staticmethod
    def _platform_style(adapter: PlatformAdapter) -> dict[str, Any]:
        profile = adapter.profile
        return {
            "display_name": adapter.display_name,
            "tone": profile.get("style", {}).get("tone", ""),
            "title_hint": profile.get("style", {}).get("title_hint", ""),
            "limits": profile.get("limits", {}),
            "publish_modes": profile.get("publish_modes", []),
        }

    @staticmethod
    def _validation_summary(issues: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "issue_count": len(issues),
            "warnings": len([issue for issue in issues if issue.get("level") == "warning"]),
            "errors": len([issue for issue in issues if issue.get("level") == "error"]),
            "issues": issues,
        }

    @staticmethod
    def _review_compliance(
        content_ir: dict[str, Any],
        validation_report: dict[str, list[dict[str, Any]]],
    ) -> dict[str, list[dict[str, Any]]]:
        body = content_ir.get("body", "")
        report: dict[str, list[dict[str, Any]]] = {
            "global": [
                {
                    "level": "info",
                    "code": "SIMULATION_ONLY",
                    "field": "publish",
                    "message": "第一阶段仅执行模拟编排，不会调用真实平台或账号。",
                },
                {
                    "level": "info",
                    "code": "MANUAL_REVIEW_REQUIRED",
                    "field": "content",
                    "message": "真实发布前仍需人工确认版权、事实准确性和平台规范。",
                },
            ]
        }

        if content_ir.get("word_count", 0) < 50:
            report["global"].append(
                {
                    "level": "warning",
                    "code": "CONTENT_TOO_BRIEF",
                    "field": "body",
                    "message": "正文较短，建议补充背景、观点或行动建议后再发布。",
                }
            )

        if not content_ir.get("assets"):
            report["global"].append(
                {
                    "level": "info",
                    "code": "ASSET_REVIEW_SUGGESTED",
                    "field": "assets",
                    "message": "当前内容没有素材，图文平台发布前建议补充封面或正文配图。",
                }
            )

        if "转载" in body or "引用" in body:
            report["global"].append(
                {
                    "level": "warning",
                    "code": "COPYRIGHT_REVIEW_SUGGESTED",
                    "field": "body",
                    "message": "正文提到转载或引用，发布前建议确认授权和来源标注。",
                }
            )

        for platform, issues in validation_report.items():
            report[platform] = [
                {
                    "level": "info",
                    "code": "FORMAT_LINT_SUMMARY",
                    "field": "draft",
                    "message": f"格式校验发现 {len(issues)} 项提示。",
                }
            ]

        return report

    @staticmethod
    def _build_recommendations(
        validation_report: dict[str, list[dict[str, Any]]],
        compliance_report: dict[str, list[dict[str, Any]]],
    ) -> list[str]:
        recommendations: list[str] = []

        for platform, issues in validation_report.items():
            for issue in issues:
                if issue.get("level") in {"warning", "error"}:
                    recommendations.append(
                        f"{platform}: {issue.get('message', '请检查平台草稿。')}"
                    )

        for issue in compliance_report.get("global", []):
            if issue.get("level") == "warning":
                recommendations.append(issue.get("message", "请进行人工复核。"))

        if not recommendations:
            recommendations.append("当前草稿已完成模拟编排，可进入人工预览和确认。")

        return recommendations
