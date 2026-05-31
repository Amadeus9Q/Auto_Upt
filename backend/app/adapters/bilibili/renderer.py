from typing import Any

from backend.app.adapters.base import first_non_empty, split_paragraphs


def _clean_text(text: str) -> str:
    """去除 markdown 标记，保留纯文本。"""
    import re
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    return text.strip()


def _format_timestamp(index: int) -> str:
    """将章节序号转为模拟时间戳（分钟:秒）。"""
    mins = index // 2
    secs = (index % 2) * 30
    return f"{mins:02d}:{secs:02d}"


def _build_bilibili_body(chapters: list[dict[str, Any]], all_media: list[dict[str, Any]], fallback_body: str) -> tuple[list[str], list[str]]:
    """B站风格：视频简介 + 时间轴章节 + 内容要点。

    B站视频简介偏好：
    - 顶部简短介绍（1-2 句）
    - 时间轴分段，每段 = 章节标题 + 简短说明
    - 要点提炼为可扫读的列表
    - 标签集中收尾
    - 适合搜索的标题和关键词
    """
    if not chapters:
        return split_paragraphs(fallback_body), []

    parts: list[str] = []
    # 收集要点
    points: list[str] = []

    for idx, ch in enumerate(chapters):
        heading = _clean_text(ch.get("title", ""))
        content = _clean_text(ch.get("content", ""))
        ts = _format_timestamp(idx)

        # 时间轴条目
        if heading and content:
            parts.append(f"{ts} | {heading}")
            # 取内容首句作为说明
            first_sentence = content.replace("\n", " ").split("。")[0].strip()
            if first_sentence:
                parts.append(f"     {first_sentence}。")
            points.append(heading)
        elif heading:
            parts.append(f"{ts} | {heading}")
            points.append(heading)
        elif content:
            parts.append(f"{ts} | {content[:80]}")
            points.append(content[:60])

        parts.append("")

        # 子章节缩进处理
        for sub in ch.get("sub_chapters", []):
            sub_h = _clean_text(sub.get("title", ""))
            sub_c = _clean_text(sub.get("content", ""))
            if sub_h:
                parts.append(f"    └ {sub_h}")
                points.append(sub_h)
            if sub_c:
                parts.append(f"       {sub_c[:100]}")

        if ch.get("sub_chapters"):
            parts.append("")

    # 将要点去重作为 content_points 返回
    return parts, points[:10]


def render_draft(content_ir: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    platform_copy = (content_ir.get("platform_copies") or {}).get(profile["platform"]) or {}
    chapters = content_ir.get("flat_chapters") or content_ir.get("chapters") or []
    all_media = content_ir.get("all_media", [])
    title = first_non_empty(platform_copy.get("title"), content_ir.get("title"), content_ir.get("summary")) or ""
    summary = platform_copy.get("subtitle") or content_ir.get("summary", "")
    tags = platform_copy.get("tags") or content_ir.get("tags", [])
    media_slots = content_ir.get("media_slots", {})

    # B站风格正文
    body_parts, content_points = _build_bilibili_body(chapters, all_media, content_ir["body"])

    # 组装完整简介
    if platform_copy.get("plain_body"):
        full_body = [platform_copy["plain_body"]]
    else:
        full_body: list[str] = []
        if summary:
            full_body.append(summary)
            full_body.append("")
        full_body.append("【视频章节】")
        full_body.append("")
        full_body.extend(body_parts)
        full_body.append(f"🏷️ {' · '.join(tags)}" if tags else "🏷️ 待补充")

    return {
        "platform": profile["platform"],
        "display_name": profile.get("display_name", profile["platform"]),
        "title": title,
        "body": "\n".join(full_body),
        "summary": summary,
        "tags": tags,
        "assets": content_ir.get("assets", []),
        "body_blocks": content_ir.get("body_blocks", []),
        "media_slots": media_slots,
        "cover_image": media_slots.get("cover"),
        "main_video": media_slots.get("main_video"),
        "content_points": content_points,
        "platform_copy": platform_copy,
        "style_notes": [
            "视频简介 + 时间轴章节（MM:SS 标记）。",
            "章节标题用作内容要点，子章节缩进展开。",
            "标签用 · 分隔，便于搜索。",
        ],
        "metadata": {
            "source_word_count": content_ir.get("word_count", 0),
            "suggested_format": "video_description",
        },
    }
