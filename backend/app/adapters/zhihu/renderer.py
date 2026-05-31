from typing import Any

from backend.app.adapters.base import first_non_empty, split_paragraphs


def _escape_markdown(text: str) -> str:
    """清理文本中的 markdown 标记，保留纯文本。"""
    import re
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return text.strip()


def _build_zhihu_blocks(
    chapters: list[dict[str, Any]],
    all_media: list[dict[str, Any]],
    summary: str,
    fallback_body: str,
) -> list[dict[str, Any]]:
    """构建知乎风格的结构化内容块。

    返回块类型：conclusion / heading-1 / heading-2 / text / separator / quote / image
    """
    blocks: list[dict[str, Any]] = []

    # 无章节时兜底
    if not chapters:
        for para in split_paragraphs(fallback_body):
            blocks.append({"type": "text", "text": para})
        return blocks

    # 开篇结论
    if summary:
        blocks.append({"type": "conclusion", "text": f"先说结论：{_escape_markdown(summary)}"})

    for idx, ch in enumerate(chapters):
        heading = ch.get("title", "")
        content = ch.get("content", "")
        level = ch.get("level", 1)
        media_items = ch.get("media_items", [])

        # 一级章节分隔
        if level == 1 and idx > 0:
            blocks.append({"type": "separator"})

        # 章节标题
        if heading:
            block_type = "heading-1" if level <= 1 else "heading-2"
            blocks.append({"type": block_type, "text": _escape_markdown(heading)})

        # 章节正文（按段落拆分）
        if content:
            clean = _escape_markdown(content)
            for para in split_paragraphs(clean):
                blocks.append({"type": "text", "text": para})

        # 章节内联图片
        for m in media_items:
            if m.get("kind") == "image":
                blocks.append({
                    "type": "image",
                    "src": m.get("src", ""),
                    "name": m.get("name", "插图"),
                })

        # 子章节：引用块
        for sub in ch.get("sub_chapters", []):
            sub_h = _escape_markdown(sub.get("title", ""))
            sub_c = _escape_markdown(sub.get("content", ""))
            if sub_h or sub_c:
                blocks.append({"type": "quote", "text": sub_h, "detail": sub_c})

    return blocks


def _blocks_to_text(blocks: list[dict[str, Any]]) -> str:
    """将结构化块转为纯文本 body（向后兼容）。"""
    lines: list[str] = []
    for b in blocks:
        t = b["type"]
        if t == "conclusion":
            lines.append(f"**{b['text']}**")
            lines.append("")
        elif t == "heading-1":
            lines.append("")
            lines.append(f"▎{b['text']}")
            lines.append("")
        elif t == "heading-2":
            lines.append(f"**{b['text']}**")
            lines.append("")
        elif t == "text":
            lines.append(b["text"])
            lines.append("")
        elif t == "separator":
            lines.append("---")
            lines.append("")
        elif t == "quote":
            lines.append(f"> {b['text']}" if b["text"] else ">")
            if b.get("detail"):
                lines.append(f"> {b['detail']}")
            lines.append("")
        elif t == "image":
            lines.append(f"[ 图片：{b.get('name', '插图')} ]")
            lines.append("")
    return "\n".join(lines)


def render_draft(content_ir: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    platform_copy = (content_ir.get("platform_copies") or {}).get(profile["platform"]) or {}
    chapters = content_ir.get("flat_chapters") or content_ir.get("chapters") or []
    all_media = content_ir.get("all_media", [])
    title = first_non_empty(platform_copy.get("title"), content_ir.get("title"), content_ir.get("summary")) or ""
    summary = platform_copy.get("subtitle") or content_ir.get("summary", "")

    # 构建结构化块
    zhihu_blocks = _build_zhihu_blocks(chapters, all_media, summary, content_ir["body"])

    # 纯文本向后兼容
    if platform_copy.get("plain_body"):
        body = platform_copy["plain_body"]
    else:
        body = _blocks_to_text(zhihu_blocks)

    return {
        "platform": profile["platform"],
        "display_name": profile.get("display_name", profile["platform"]),
        "title": title,
        "body": body,
        "summary": summary,
        "zhihu_blocks": zhihu_blocks,
        "tags": platform_copy.get("tags") or content_ir.get("tags", []),
        "assets": content_ir.get("assets", []),
        "body_blocks": content_ir.get("body_blocks", []),
        "media_slots": content_ir.get("media_slots", {}),
        "platform_copy": platform_copy,
        "style_notes": [
            "结论先行，分观点论证。",
            "一级章节为独立论点（▎标记），子章节为引用支撑（> 引用块）。",
            "文末自然收尾，不强行总结。",
        ],
        "metadata": {
            "source_word_count": content_ir.get("word_count", 0),
            "suggested_format": "answer_or_column",
        },
    }
