from typing import Any

from backend.app.adapters.base import clip_text, first_non_empty, split_paragraphs


def render_draft(content_ir: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    limits = profile.get("limits", {})
    paragraphs = split_paragraphs(content_ir["body"])
    title = clip_text(
        first_non_empty(content_ir.get("title"), content_ir.get("summary")),
        limits.get("title_max_length", 20),
    )
    highlights = paragraphs[:3] or [content_ir.get("summary", "")]
    tag_line = " ".join(f"#{tag}" for tag in content_ir.get("tags", [])[:5])
    body_parts = [
        content_ir.get("summary", ""),
        "",
        "笔记亮点：",
        *[f"- {clip_text(item, 80)}" for item in highlights],
        "",
        tag_line,
    ]

    return {
        "platform": profile["platform"],
        "display_name": profile.get("display_name", profile["platform"]),
        "title": title,
        "body": clip_text("\n".join(body_parts).strip(), limits.get("body_max_length", 1000)),
        "summary": clip_text(content_ir.get("summary", ""), 80),
        "tags": content_ir.get("tags", [])[: limits.get("tags_max_count", 10)],
        "assets": content_ir.get("assets", []),
        "body_blocks": content_ir.get("body_blocks", []),
        "media_slots": content_ir.get("media_slots", {}),
        "style_notes": [
            "Prefer short title and dense highlights.",
            "Use image assets before real publish.",
        ],
        "metadata": {
            "source_word_count": content_ir.get("word_count", 0),
            "suggested_format": "image_note",
        },
    }
