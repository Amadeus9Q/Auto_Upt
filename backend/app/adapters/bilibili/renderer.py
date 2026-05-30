from typing import Any

from backend.app.adapters.base import clip_tags, first_non_empty, split_paragraphs


def render_draft(content_ir: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    limits = profile.get("limits", {})
    paragraphs = split_paragraphs(content_ir["body"])
    title = first_non_empty(content_ir.get("title"), content_ir.get("summary"))
    tags = clip_tags(content_ir.get("tags", []), max_count=4)
    media_slots = content_ir.get("media_slots", {})
    body_parts = [
        "视频简介",
        content_ir.get("summary", ""),
        "",
        "内容要点",
        *[f"- {item}" for item in (paragraphs[:5] or [content_ir["body"]])],
        "",
        f"标签：{', '.join(tags)}" if tags else "标签：待补充",
    ]

    return {
        "platform": profile["platform"],
        "display_name": profile.get("display_name", profile["platform"]),
        "title": title,
        "body": "\n".join(body_parts),
        "summary": content_ir.get("summary", ""),
        "tags": tags,
        "assets": content_ir.get("assets", []),
        "body_blocks": content_ir.get("body_blocks", []),
        "media_slots": media_slots,
        "cover_image": media_slots.get("cover"),
        "main_video": media_slots.get("main_video"),
        "style_notes": [
            "Keep searchable title and concise description.",
            "Map article sections into video description bullet points.",
        ],
        "metadata": {
            "source_word_count": content_ir.get("word_count", 0),
            "suggested_format": "video_description_or_dynamic",
        },
    }
