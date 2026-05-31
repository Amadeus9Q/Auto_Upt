from typing import Any

from backend.app.adapters.base import clip_tags, first_non_empty, split_paragraphs


def render_draft(content_ir: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    limits = profile.get("limits", {})
    paragraphs = split_paragraphs(content_ir["body"])
    title = first_non_empty(content_ir.get("title"), content_ir.get("summary"))
    highlights = paragraphs[:6] or [content_ir.get("summary", "")]
    tag_line = " ".join(f"#{tag}" for tag in content_ir.get("tags", [])[:5])
    body_parts = [
        content_ir.get("summary", ""),
        "",
        "笔记亮点：",
        *[f"- {item}" for item in highlights],
        "",
        "详细内容：",
        *[p for p in paragraphs[6:12]],
        "",
        tag_line,
    ]

    return {
        "platform": profile["platform"],
        "display_name": profile.get("display_name", profile["platform"]),
        "title": title,
        "body": "\n".join(body_parts).strip(),
        "summary": content_ir.get("summary", ""),
        "tags": clip_tags(content_ir.get("tags", []), max_count=4),
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
