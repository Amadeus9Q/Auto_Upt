from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.schemas.content import ContentInput, PlatformLiteral


AgentStepStatusLiteral = Literal["succeeded", "skipped", "failed"]


class AgentRunRequest(ContentInput):
    platforms: list[PlatformLiteral] | None = Field(
        default=None,
        description="需要纳入模拟 Agent 编排的平台列表。为空时默认覆盖全部已支持平台。",
    )
    include_simulation: bool = Field(
        default=True,
        description="是否在编排末尾执行模拟发布步骤。当前不会调用任何真实外部平台。",
    )


class AgentStep(BaseModel):
    name: str = Field(description="Agent 步骤名称。")
    role: str = Field(description="Agent 角色，例如 Content Analyst 或 Format Linter。")
    status: AgentStepStatusLiteral = Field(description="步骤执行状态。")
    input_summary: str = Field(description="该步骤接收的输入摘要。")
    output: dict[str, Any] = Field(description="该步骤生成的结构化模拟输出。")
    started_at: datetime = Field(description="步骤开始时间。")
    completed_at: datetime = Field(description="步骤完成时间。")


class AgentRunResponse(BaseModel):
    run_id: str = Field(description="本次模拟 Agent 编排运行 ID。")
    status: AgentStepStatusLiteral = Field(description="整体编排状态。")
    mode: Literal["simulate"] = Field(description="编排模式。第一阶段固定为 simulate。")
    platforms: list[PlatformLiteral] = Field(description="本次编排覆盖的平台列表。")
    steps: list[AgentStep] = Field(description="模拟 Agent 编排步骤列表。")
    content_ir: dict[str, Any] = Field(description="统一内容 IR。")
    drafts: dict[str, dict[str, Any]] = Field(description="按平台分组的平台草稿。")
    validation_report: dict[str, list[dict[str, Any]]] = Field(
        description="按平台分组的格式校验报告。",
    )
    compliance_report: dict[str, list[dict[str, Any]]] = Field(
        description="模拟合规检查报告，包含全局和平台级提示。",
    )
    simulation_results: dict[str, dict[str, Any]] = Field(
        description="按平台分组的模拟发布结果。未执行模拟发布时为空对象。",
    )
    recommendations: list[str] = Field(description="下一步人工检查或优化建议。")
    created_at: datetime = Field(description="编排创建时间。")
