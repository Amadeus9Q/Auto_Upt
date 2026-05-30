from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from backend.app.adapters.base import PlatformAdapter
from backend.app.adapters.registry import select_adapters
from backend.app.schemas.agent import (
    AgentRunRequest,
    AgentRunResponse,
    AgentStep,
    AgentStepStatusLiteral,
)
from backend.app.services.preview_service import PreviewService


class SimulatedAgentOrchestrator:
    def __init__(self) -> None:
        self.preview_service = PreviewService()

    def run_preview_workflow(self, request: AgentRunRequest) -> AgentRunResponse:
        created_at = datetime.now(UTC)
        run_id = str(uuid4())
        steps: list[AgentStep] = []

        content_ir = self.preview_service.normalize_content(request)
        steps.append(
            self._step(
                name="内容分析",
                role="Content Analyst",
                input_summary="原始标题、正文、标签和素材。",
                output={
                    "title": content_ir["title"],
                    "summary": content_ir["summary"],
                    "content_type": content_ir["content_type"],
                    "word_count": content_ir["word_count"],
                    "tags": content_ir["tags"],
                    "asset_count": len(content_ir["assets"]),
                },
            )
        )

        adapters = select_adapters(request.platforms)
        platforms = list(adapters.keys())
        steps.append(
            self._step(
                name="平台风格规划",
                role="Platform Stylist",
                input_summary="统一内容 IR 和目标平台列表。",
                output={
                    platform: self._platform_style(adapter)
                    for platform, adapter in adapters.items()
                },
            )
        )

        drafts = {
            platform: adapter.render(content_ir)
            for platform, adapter in adapters.items()
        }
        steps.append(
            self._step(
                name="平台草稿渲染",
                role="Platform Stylist",
                input_summary="统一内容 IR、平台 profile 和平台风格规划。",
                output={
                    platform: {
                        "title": draft.get("title"),
                        "body_length": len(draft.get("body", "")),
                        "tag_count": len(draft.get("tags", [])),
                    }
                    for platform, draft in drafts.items()
                },
            )
        )

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

        compliance_report = self._review_compliance(content_ir, validation_report)
        steps.append(
            self._step(
                name="合规检查",
                role="Compliance Reviewer",
                input_summary="统一内容 IR、平台草稿和格式校验报告。",
                output=compliance_report,
            )
        )

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
