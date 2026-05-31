from typing import Any

from backend.app.adapters.base import clip_tags, first_non_empty, split_paragraphs


def render_draft(content_ir: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    paragraphs = split_paragraphs(content_ir["body"])
    title = first_non_empty(content_ir.get("title"), content_ir.get("summary"))

    body_parts = [
        "先说结论：",
        content_ir.get("summary", ""),
        "",
        "展开说明：",
        *(paragraphs or [content_ir["body"]]),
        "",
        "补充：以上内容适合作为知乎回答/专栏草稿，发布前可继续加入引用和案例。",
    ]

    return {
        "platform": profile["platform"],
        "display_name": profile.get("display_name", profile["platform"]),
        "title": title,
        "body": "\n".join(body_parts),
        "summary": content_ir.get("summary", ""),
        "tags": clip_tags(content_ir.get("tags", []), max_count=4),
        "assets": content_ir.get("assets", []),
        "body_blocks": content_ir.get("body_blocks", []),
        "media_slots": content_ir.get("media_slots", {}),
        "style_notes": [
            "Lead with a conclusion.",
            "Use explanation and examples instead of direct marketing copy.",
        ],
        "metadata": {
            "source_word_count": content_ir.get("word_count", 0),
            "suggested_format": "answer_or_column",
        },
    }
