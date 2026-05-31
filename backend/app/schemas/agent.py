from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.app.schemas.content import ContentInput, PlatformLiteral


AgentStepStatusLiteral = Literal["succeeded", "skipped", "failed"]
AgentStyleGoalLiteral = Literal["professional", "knowledge", "social", "video", "original"]
AgentRewriteStrengthLiteral = Literal["light", "medium", "strong"]
AgentLlmModeLiteral = Literal["auto", "enabled", "disabled"]
AgentWritingStyleLiteral = Literal["default", "professional", "concise", "vivid", "custom"]


class AgentRunRequest(ContentInput):
    platforms: list[PlatformLiteral] | None = Field(
        default=None,
        description="需要纳入模拟 Agent 编排的平台列表。为空时默认覆盖全部已支持平台。",
    )
    include_simulation: bool = Field(
        default=True,
        description="是否在编排末尾执行模拟发布步骤。当前不会调用任何真实外部平台。",
    )


class AgentAdaptPreviewRequest(ContentInput):
    preview_id: str | None = Field(
        default=None,
        description="需要被更新的既有预览 ID。传入后，Agent 结果会合并写回该 preview 的对应平台草稿。",
    )
    platforms: list[PlatformLiteral] | None = Field(
        default=None,
        description="需要适配的平台列表。为空时默认覆盖全部已支持平台。",
    )
    style_goal: AgentStyleGoalLiteral = Field(
        default="professional",
        description="目标风格：professional、knowledge、social、video 或 original。",
    )
    rewrite_strength: AgentRewriteStrengthLiteral = Field(
        default="medium",
        description="改写强度：light 保守润色，medium 调整结构和表达，strong 更明显重写。",
    )
    writing_style: AgentWritingStyleLiteral = Field(
        default="default",
        description="文字风格：default 使用对应平台默认风格，professional 专业，concise 简洁，vivid 生动，custom 自定义。",
    )
    custom_writing_style: str | None = Field(
        default=None,
        max_length=300,
        description="自定义文字风格描述。仅 writing_style=custom 时使用，空白时回退为 default。",
    )
    overwrite_existing_metadata: bool = Field(
        default=False,
        description="兼容旧字段：用户已有标题或关键词时是否允许 Agent 同时覆盖标题和关键词。",
    )
    update_title: bool = Field(
        default=False,
        description="是否允许 Agent 修改标题。为 false 时保留请求中已有标题，仅在标题为空时补全。",
    )
    update_tags: bool = Field(
        default=False,
        description="是否允许 Agent 修改关键词。为 false 时保留请求中已有关键词，仅在关键词为空时补全。",
    )
    use_llm: AgentLlmModeLiteral = Field(
        default="auto",
        description="LLM 使用策略。auto 表示有可用配置时启用，否则使用规则引擎。",
    )
    persist_preview: bool = Field(
        default=True,
        description="是否将 Agent 结果保存为预览记录，保存后可直接进入发布流程。",
    )


class AgentStep(BaseModel):
    name: str = Field(description="Agent 步骤名称。")
    role: str = Field(description="Agent 角色，例如 Content Analyst 或 Format Linter。")
    status: AgentStepStatusLiteral = Field(description="步骤执行状态。")
    input_summary: str = Field(description="该步骤接收的输入摘要。")
    output: dict[str, Any] = Field(description="该步骤生成的结构化模拟输出。")
    started_at: datetime = Field(description="步骤开始时间。")
    completed_at: datetime = Field(description="步骤完成时间。")


class AgentToolInfo(BaseModel):
    name: str = Field(description="工具名称，例如 content.normalize。")
    description: str = Field(description="工具说明。")
    input_schema: dict[str, Any] = Field(default_factory=dict, description="工具输入结构说明。")
    output_schema: dict[str, Any] = Field(default_factory=dict, description="工具输出结构说明。")
    llm_enabled: bool = Field(default=False, description="该工具当前是否可能使用 LLM 增强。")


class AgentToolListResponse(BaseModel):
    tools: list[AgentToolInfo] = Field(description="当前后端允许 Agent 调用的工具列表。")


class AgentToolCall(BaseModel):
    name: str = Field(description="工具名称。")
    description: str = Field(description="工具说明。")
    status: AgentStepStatusLiteral = Field(description="工具调用状态。")
    input_summary: str = Field(description="工具输入摘要。")
    output: dict[str, Any] = Field(default_factory=dict, description="工具输出。")
    started_at: datetime = Field(description="工具调用开始时间。")
    completed_at: datetime = Field(description="工具调用结束时间。")


class AgentGeneratedMetadata(BaseModel):
    title: str = Field(description="Agent 建议标题。")
    tags: list[str] = Field(default_factory=list, description="Agent 建议关键词。")
    summary: str = Field(default="", description="Agent 生成摘要。")
    source: str = Field(default="rule", description="生成来源：rule 或 llm。")


class AgentRewrittenContent(BaseModel):
    title: str = Field(description="建议使用的标题。")
    body: str = Field(description="改写后的正文。")
    tags: list[str] = Field(default_factory=list, description="建议使用的关键词。")
    style_goal: AgentStyleGoalLiteral = Field(description="目标风格。")
    rewrite_strength: AgentRewriteStrengthLiteral = Field(description="改写强度。")
    source: str = Field(default="rule", description="改写来源：rule 或 llm。")


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


class AgentAdaptPreviewResponse(BaseModel):
    run_id: str = Field(description="Agent 运行 ID。")
    status: AgentStepStatusLiteral = Field(description="整体运行状态。")
    preview_id: str | None = Field(default=None, description="保存后的预览 ID。persist_preview=false 时为空。")
    tool_calls: list[AgentToolCall] = Field(description="工具调用轨迹。")
    metadata: AgentGeneratedMetadata = Field(description="标题、关键词和摘要建议。")
    rewritten_content: AgentRewrittenContent = Field(description="改写后的内容建议。")
    content_ir: dict[str, Any] = Field(description="统一内容 IR。")
    drafts: dict[str, dict[str, Any]] = Field(description="按平台分组的平台草稿。")
    validation_report: dict[str, list[dict[str, Any]]] = Field(description="按平台分组的校验报告。")
    compliance_report: dict[str, list[dict[str, Any]]] = Field(description="合规检查报告。")
    recommendations: list[str] = Field(description="下一步人工检查或优化建议。")
    created_at: datetime = Field(description="运行创建时间。")
    llm_status: Literal["available", "degraded", "disabled"] = Field(
        default="disabled",
        description="LLM 调用状态：available 至少一次成功，degraded 全部失败已降级，disabled 未配置或未启用。",
    )
