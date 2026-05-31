from typing import Any

from backend.app.adapters.base import first_non_empty, split_paragraphs

# 小红书常用的段落开头 emoji
XHS_EMOJI = ["📌", "✨", "💡", "🔥", "📝", "🎯", "💬", "🌟", "📢", "🎬"]


def _strip_markdown(text: str) -> str:
    """去除 markdown 标记，保留纯文本。"""
    import re
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return text.strip()


def _build_xhs_body(chapters: list[dict[str, Any]], all_media: list[dict[str, Any]], fallback_body: str) -> list[str]:
    """小红书风格：短标题 + emoji 分段 + 亮点提炼 + 话题标签。

    小红书笔记偏好：
    - 开篇用 emoji 吸引注意力
    - 每个章节提炼为 1-2 句精华（取标题或内容首句）
    - 用空行和 emoji 制造呼吸感
    - 正文紧凑，不写长段落
    - 末尾集中放置 #话题标签
    """
    if not chapters:
        return split_paragraphs(fallback_body)

    parts: list[str] = []

    for idx, ch in enumerate(chapters):
        heading = _strip_markdown(ch.get("title", ""))
        content = _strip_markdown(ch.get("content", ""))
        emoji = XHS_EMOJI[idx % len(XHS_EMOJI)]

        # 取标题或内容首句作为分段要点
        if heading:
            parts.append(f"{emoji} {heading}")
            if content:
                # 只取前 2 句，保持短小
                sentences = content.replace("\n", " ").split("。")
                short = "。".join(sentences[:2]).strip()
                if short:
                    parts.append(short + "。")
        else:
            parts.append(f"{emoji} {content}" if content else f"{emoji}")

        parts.append("")

        # 子章节作为补充小点
        for sub in ch.get("sub_chapters", []):
            sub_h = _strip_markdown(sub.get("title", ""))
            sub_c = _strip_markdown(sub.get("content", ""))
            if sub_h or sub_c:
                text = sub_h or sub_c
                parts.append(f"· {text}")
        if ch.get("sub_chapters"):
            parts.append("")

    return parts


def render_draft(content_ir: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    platform_copy = (content_ir.get("platform_copies") or {}).get(profile["platform"]) or {}
    chapters = content_ir.get("flat_chapters") or content_ir.get("chapters") or []
    all_media = content_ir.get("all_media", [])
    title = first_non_empty(platform_copy.get("title"), content_ir.get("title"), content_ir.get("summary")) or ""
    summary = platform_copy.get("subtitle") or content_ir.get("summary", "")
    tags = platform_copy.get("tags") or content_ir.get("tags", [])

    # 小红书风格正文
    body_content = _build_xhs_body(chapters, all_media, content_ir["body"])

    # 标题区
    header = []
    if summary:
        header.append(f"💬 {_strip_markdown(summary)}")
        header.append("")

    # 话题标签区
    tag_line = " ".join(f"#{tag}" for tag in tags) if tags else ""
    footer = ["", tag_line] if tag_line else []

    body_parts = [*header, *body_content, *footer]
    body = platform_copy.get("plain_body") or "\n".join(body_parts).strip()

    # 亮点：取章节标题作为 highlights
    highlights = [
        _strip_markdown(ch.get("title", ""))
        for ch in chapters[:5]
        if ch.get("title")
    ] or [summary]

    return {
        "platform": profile["platform"],
        "display_name": profile.get("display_name", profile["platform"]),
        "title": title,
        "body": body,
        "summary": summary,
        "tags": tags,
        "assets": content_ir.get("assets", []),
        "body_blocks": content_ir.get("body_blocks", []),
        "media_slots": content_ir.get("media_slots", {}),
        "highlights": highlights,
        "platform_copy": platform_copy,
        "style_notes": [
            "Emoji 分段 + 短句，保持呼吸感。",
            "每个章节提炼 1-2 句精华，不写长段落。",
            "末尾集中放置 #话题标签。",
        ],
        "metadata": {
            "source_word_count": content_ir.get("word_count", 0),
            "suggested_format": "image_note",
        },
    }
