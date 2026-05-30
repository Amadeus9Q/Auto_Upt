from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from backend.app.core.config import get_settings
from backend.app.schemas.agent import AgentToolInfo


ToolRunner = Callable[[dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    runner: ToolRunner | None = None
    supports_llm: bool = False

    def to_info(self) -> AgentToolInfo:
        settings = get_settings()
        return AgentToolInfo(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            llm_enabled=self.supports_llm and bool(settings.openai_api_key),
        )


class AgentToolRegistry:
    """白名单工具注册表。

    当前是内置工具注册表，接口形态刻意贴近 MCP 的 tool list/tool call 思路。
    后续接入真实 MCP server 时，可用同名工具替换 runner。
    """

    def __init__(self) -> None:
        self._tools: dict[str, AgentTool] = {}

    def register(self, tool: AgentTool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> AgentTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise KeyError(f"Agent tool is not registered: {name}") from exc

    def list_tools(self) -> list[AgentToolInfo]:
        return [tool.to_info() for tool in self._tools.values()]


def build_default_tool_registry() -> AgentToolRegistry:
    registry = AgentToolRegistry()
    for tool in (
        AgentTool(
            name="content.normalize",
            description="将用户输入整理为统一内容 IR。",
            input_schema={"content": "ContentInput"},
            output_schema={"content_ir": "dict"},
        ),
        AgentTool(
            name="content.analyze",
            description="分析章节、摘要、素材和内容类型。",
            input_schema={"content_ir": "dict"},
            output_schema={"analysis": "ContentAnalysis"},
        ),
        AgentTool(
            name="metadata.extract",
            description="在标题或关键词缺失时生成精炼标题、摘要和关键词。",
            input_schema={"analysis": "ContentAnalysis", "overwrite_existing_metadata": "bool"},
            output_schema={"title": "str", "tags": "list[str]", "summary": "str"},
            supports_llm=True,
        ),
        AgentTool(
            name="title.generate",
            description="当内容没有标题时，根据正文自动生成精炼标题。仅输入正文文本，返回标题字符串。",
            input_schema={"body": "str", "content_type": "str"},
            output_schema={"title": "str"},
            supports_llm=True,
        ),
        AgentTool(
            name="keywords.generate",
            description="当内容没有关键词/标签时，根据正文自动提取或生成关键词列表。",
            input_schema={"body": "str", "title": "str", "content_type": "str"},
            output_schema={"tags": "list[str]"},
            supports_llm=True,
        ),
        AgentTool(
            name="style.rewrite",
            description="按目标风格和改写强度生成建议正文。",
            input_schema={"body": "str", "style_goal": "str", "rewrite_strength": "str"},
            output_schema={"title": "str", "body": "str", "tags": "list[str]"},
            supports_llm=True,
        ),
        AgentTool(
            name="platform.render",
            description="调用平台 Adapter 渲染多平台草稿。",
            input_schema={"content_ir": "dict", "platforms": "list[str]"},
            output_schema={"drafts": "dict[str, dict]"},
        ),
        AgentTool(
            name="platform.validate",
            description="调用平台 Adapter 和媒体规则生成校验报告。",
            input_schema={"drafts": "dict[str, dict]"},
            output_schema={"validation_report": "dict[str, list]"},
        ),
        AgentTool(
            name="compliance.review",
            description="生成合规检查提示和人工复核建议。",
            input_schema={"content_ir": "dict", "validation_report": "dict"},
            output_schema={"compliance_report": "dict", "recommendations": "list[str]"},
        ),
    ):
        registry.register(tool)
    return registry
