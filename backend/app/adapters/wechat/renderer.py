from typing import Any

from backend.app.adapters.base import clip_text, first_non_empty, split_paragraphs


def _pick_cover(assets: list[dict]) -> dict | None:
    for asset in assets:
        if asset.get("usage") in ("default_cover", "cover") and asset.get("type") == "image":
            return asset
    return next((a for a in assets if a.get("type") == "image"), None)


def _build_rich_body(paragraphs: list[str], assets: list[dict]) -> list[dict]:
    """将段落和素材组装为结构化渲染数组，供前端手机框预览使用。"""
    rich: list[dict] = []
    for para in paragraphs:
        if para.startswith("# "):
            rich.append({"type": "heading", "level": 1, "text": para[2:]})
        elif para.startswith("## "):
            rich.append({"type": "heading", "level": 2, "text": para[3:]})
        elif para.startswith("> "):
            rich.append({"type": "quote", "text": para[2:]})
        else:
            rich.append({"type": "paragraph", "text": para})

    for asset in assets:
        if asset.get("type") == "image" and asset.get("usage") not in ("default_cover", "cover"):
            rich.append({
                "type": "image",
                "src": asset.get("url", ""),
                "alt": asset.get("name", ""),
            })

    return rich


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
        "rich_body": _build_rich_body(paragraphs, content_ir.get("assets", [])),
        "cover_image": _pick_cover(content_ir.get("assets", [])),
        "author": content_ir.get("author", "Auto_Upt"),
        "publish_date": content_ir.get("created_at", ""),
        "style_notes": [
            "Use a clear intro before the main content.",
            "Keep paragraphs scannable for long-form reading.",
        ],
        "metadata": {
            "source_word_count": content_ir.get("word_count", 0),
            "estimated_read_time_minutes": max(1, content_ir.get("word_count", 0) // 500),
        },
    }
