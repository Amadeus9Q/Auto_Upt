from typing import Any

from backend.app.adapters.base import first_non_empty, split_paragraphs


def render_draft(content_ir: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    paragraphs = split_paragraphs(content_ir["body"])
    title = first_non_empty(content_ir.get("title"), content_ir.get("summary"))
    tags = [tag.strip() for tag in content_ir.get("tags", []) if tag.strip()]
    tag_line = " ".join(f"#{tag}" for tag in tags)
    body_parts: list[str] = []
    summary = content_ir.get("summary", "")
    if summary:
        body_parts.extend([summary, ""])
    body_parts.extend(paragraphs)
    if tag_line:
        body_parts.extend(["", tag_line])

    return {
        "platform": profile["platform"],
        "display_name": profile.get("display_name", profile["platform"]),
        "title": title,
        "body": "\n".join(body_parts).strip(),
        "summary": content_ir.get("summary", ""),
        "tags": tags,
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
