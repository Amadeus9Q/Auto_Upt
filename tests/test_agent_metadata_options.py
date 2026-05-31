from types import SimpleNamespace
from typing import Any

from backend.app.adapters.xiaohongshu.renderer import render_draft as render_xiaohongshu_draft
from backend.app.agents.tool_orchestrator import ToolDrivenAgentOrchestrator
from backend.app.schemas.agent import AgentAdaptPreviewRequest


class FakeAdapter:
    def render(self, content_ir: dict[str, Any]) -> dict[str, Any]:
        return {
            "platform": "wechat",
            "display_name": "公众号",
            "title": content_ir["title"],
            "body": content_ir["body"],
            "summary": content_ir.get("summary", ""),
            "tags": content_ir.get("tags", []),
            "assets": [],
            "style_notes": [],
            "metadata": {},
        }


def _analysis() -> SimpleNamespace:
    return SimpleNamespace(
        title="Agent 新标题",
        subtitle=None,
        chapters=[SimpleNamespace(title="Agent 新标题")],
        flat_chapters=[SimpleNamespace(title="Agent 章节", content="核心内容")],
        summary="摘要内容",
        tags=["新关键词"],
    )


def _request(**overrides: Any) -> AgentAdaptPreviewRequest:
    payload = {
        "title": "保留标题",
        "body": "原始正文",
        "content_type": "article",
        "tags": ["原关键词"],
    }
    payload.update(overrides)
    return AgentAdaptPreviewRequest(**payload)


def test_rule_metadata_respects_individual_update_flags() -> None:
    orchestrator = ToolDrivenAgentOrchestrator.__new__(ToolDrivenAgentOrchestrator)

    metadata = orchestrator._rule_metadata(_request(), _analysis())
    assert metadata["title"] == "保留标题"
    assert metadata["tags"] == ["原关键词"]

    metadata = orchestrator._rule_metadata(_request(update_title=True), _analysis())
    assert metadata["title"] == "Agent 新标题"
    assert metadata["tags"] == ["原关键词"]

    metadata = orchestrator._rule_metadata(_request(update_tags=True), _analysis())
    assert metadata["title"] == "保留标题"
    assert metadata["tags"][0] == "新关键词"


def test_platform_render_preserves_title_and_tags_when_not_selected() -> None:
    copy = SimpleNamespace(
        title="平台新标题",
        plain_body="优化后的正文",
        subtitle="优化摘要",
        tags=["平台新关键词"],
        sections=[],
        media_recommendations=[],
        style_notes=[],
    )
    content_ir = {
        "title": "保留标题",
        "body": "原始正文",
        "summary": "原摘要",
        "tags": ["原关键词"],
    }

    drafts = ToolDrivenAgentOrchestrator._render_platform_drafts(
        content_ir,
        {"wechat": FakeAdapter()},
        {"wechat": copy},
        {},
        _request(),
    )
    assert drafts["wechat"]["title"] == "保留标题"
    assert drafts["wechat"]["tags"] == ["原关键词"]
    assert drafts["wechat"]["body"] == "优化后的正文"

    drafts = ToolDrivenAgentOrchestrator._render_platform_drafts(
        content_ir,
        {"wechat": FakeAdapter()},
        {"wechat": copy},
        {},
        _request(update_title=True),
    )
    assert drafts["wechat"]["title"] == "平台新标题"
    assert drafts["wechat"]["tags"] == ["原关键词"]


def test_agent_rule_social_rewrite_and_metadata_do_not_hard_truncate() -> None:
    long_title = "Agent 生成标题需要完整保留不应该被三十六字符规则硬截断"
    long_tag = "Agent关键词完整保留不应该被二十字符规则截断"
    analysis = SimpleNamespace(
        title=long_title,
        subtitle=None,
        chapters=[SimpleNamespace(title=long_title)],
        flat_chapters=[],
        summary="摘要内容",
        tags=[long_tag],
    )
    body = "\n\n".join(
        f"第{index}段完整正文需要保留，不能因为社交风格改写只取前六段或前九十个字符而丢失。"
        for index in range(1, 9)
    )

    rewritten = ToolDrivenAgentOrchestrator._rule_rewrite_body(body, "social", "medium")

    assert ToolDrivenAgentOrchestrator._build_title(analysis) == long_title
    assert ToolDrivenAgentOrchestrator._clean_tags([long_tag]) == [long_tag]
    analysis.tags = [f"完整关键词{index}" for index in range(1, 11)]
    assert ToolDrivenAgentOrchestrator.__new__(ToolDrivenAgentOrchestrator)._build_tags(analysis)[:10] == analysis.tags
    assert "第8段完整正文需要保留" in rewritten
    assert "前九十个字符而丢失" in rewritten
    assert "..." not in rewritten
    assert "…" not in rewritten


def test_xiaohongshu_renderer_preserves_all_paragraphs_and_tags() -> None:
    paragraphs = [f"第{index}段完整内容需要出现在小红书草稿中" for index in range(1, 14)]
    tags = [f"完整关键词{index}不截断" for index in range(1, 7)]
    draft = render_xiaohongshu_draft(
        {
            "title": "小红书标题完整保留",
            "summary": "摘要完整保留",
            "body": "\n\n".join(paragraphs),
            "tags": tags,
        },
        {"platform": "xiaohongshu", "display_name": "小红书"},
    )

    assert paragraphs[-1] in draft["body"]
    assert f"#{tags[-1]}" in draft["body"]
    assert draft["tags"] == tags
