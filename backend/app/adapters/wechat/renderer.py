from typing import Any

from backend.app.adapters.base import clip_text, first_non_empty, split_paragraphs


def render_draft(content_ir: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    limits = profile.get("limits", {})
    paragraphs = split_paragraphs(content_ir["body"])
    title = clip_text(
        first_non_empty(content_ir.get("title"), content_ir.get("summary")),
        limits.get("title_max_length", 64),
    )
    summary = content_ir.get("summary", "")
    body_parts = [
        f"导语：{summary}",
        "",
        "正文",
        *(paragraphs or [content_ir["body"]]),
        "",
        "发布提示：可在公众号编辑器中继续调整封面、摘要和排版。",
    ]

    return {
        "platform": profile["platform"],
        "display_name": profile.get("display_name", profile["platform"]),
        "title": title,
        "body": "\n".join(body_parts),
        "summary": clip_text(summary, 120),
        "tags": content_ir.get("tags", [])[: limits.get("tags_max_count", 5)],
        "assets": content_ir.get("assets", []),
        "style_notes": [
            "Use a clear intro before the main content.",
            "Keep paragraphs scannable for long-form reading.",
        ],
        "metadata": {
            "source_word_count": content_ir.get("word_count", 0),
            "estimated_read_time_minutes": max(1, content_ir.get("word_count", 0) // 500),
        },
    }
