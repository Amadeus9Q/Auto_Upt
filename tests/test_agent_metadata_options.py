from types import SimpleNamespace
from typing import Any

import httpx

from backend.app.adapters.xiaohongshu.renderer import render_draft as render_xiaohongshu_draft
from backend.app.agents.tool_orchestrator import ToolDrivenAgentOrchestrator, _LlmStatusTracker
from backend.app.schemas.agent import AgentAdaptPreviewRequest, AgentGeneratedMetadata


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


def test_agent_llm_timeout_does_not_disable_later_calls(monkeypatch) -> None:
    calls = 0

    class TimeoutClient:
        def __init__(self, timeout: float) -> None:
            assert timeout == 12

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def post(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            raise httpx.ConnectTimeout("unavailable")

    monkeypatch.setattr(httpx, "Client", TimeoutClient)
    orchestrator = ToolDrivenAgentOrchestrator.__new__(ToolDrivenAgentOrchestrator)
    orchestrator.settings = SimpleNamespace(
        openai_api_key="test-key",
        openai_base_url="https://example.invalid",
        openai_model="test-model",
        agent_llm_timeout_seconds=12,
    )
    orchestrator._llm_tracker = _LlmStatusTracker()

    assert orchestrator._try_llm_json(_request(), "metadata", "prompt") is None
    assert orchestrator._try_llm_json(_request(), "rewrite", "prompt") is None
    assert calls == 2
    assert orchestrator._llm_tracker.failed is False


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


def test_agent_prompt_uses_default_platform_writing_style() -> None:
    prompt = ToolDrivenAgentOrchestrator._platform_rewrite_prompt(
        "xiaohongshu",
        {"display_name": "小红书"},
        {"title": "标题", "tags": ["AI"]},
        _request(),
    )

    assert "小红书平台风格指导" in prompt
    assert "采用谈心式、亲切真诚的表达方式" in prompt
    assert "发布风格依据：使用上述对应平台默认风格" in prompt
    assert "优先级高于平台默认文字风格" not in prompt


def test_agent_prompt_prioritizes_selected_preset_writing_style() -> None:
    request = _request(writing_style="concise")
    platform_prompt = ToolDrivenAgentOrchestrator._platform_rewrite_prompt(
        "wechat",
        {"display_name": "公众号"},
        {"title": "标题", "tags": ["AI"]},
        request,
    )
    rewrite_prompt = ToolDrivenAgentOrchestrator._rewrite_prompt(
        AgentGeneratedMetadata(title="标题", tags=["AI"], summary="摘要"),
        request,
    )

    assert "微信公众号平台风格指导" in platform_prompt
    assert "优先级高于平台默认文字风格" in platform_prompt
    assert "短句优先" in platform_prompt
    assert "短句优先" in rewrite_prompt


def test_agent_prompt_uses_custom_writing_style_and_falls_back_when_empty() -> None:
    custom_style = "像产品负责人写给真实用户的一封说明信，真诚、具体、有现场感"
    custom_prompt = ToolDrivenAgentOrchestrator._platform_rewrite_prompt(
        "zhihu",
        {"display_name": "知乎"},
        {"title": "标题", "tags": ["AI"]},
        _request(writing_style="custom", custom_writing_style=custom_style),
    )
    fallback_prompt = ToolDrivenAgentOrchestrator._platform_rewrite_prompt(
        "wechat",
        {"display_name": "公众号"},
        {"title": "标题", "tags": ["AI"]},
        _request(writing_style="custom", custom_writing_style="   "),
    )

    assert custom_style in custom_prompt
    assert "优先级高于平台默认文字风格" in custom_prompt
    assert "微信公众号平台风格指导" in fallback_prompt
    assert "优先级高于平台默认文字风格" not in fallback_prompt


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
