"""公众号图文渲染器 —— 将 Content IR 转为 WeChat API 兼容的 HTML 正文。

微信公众号草稿/发布接口（draft/add、freepublish/submit）要求 content 字段
为 HTML 格式，且遵循以下限制：
- 不支持外部 CSS，所有样式必须内联 (style="...")。
- 图片使用 <img> 标签，建议用 data-src 做懒加载。
- 推荐使用 <section> 语义化分区，<h2>/<h3> 做标题。
- 视频/音频不支持直接嵌入，改为占位提示或外链。
"""

from __future__ import annotations

import html
import re
from typing import Any

from backend.app.adapters.base import clip_text, first_non_empty, split_paragraphs

# 匹配正文中的中文媒体标记：【图片：xxx.jpg】【视频：xxx.mp4】【音频：xxx.mp3】
CN_MEDIA_MARKER_RE = re.compile(r"【(?:图片|视频|音频)[：:]\s*[^】]+】")


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------

# 公众号正文插图建议宽度（像素）
WECHAT_BODY_IMAGE_WIDTH = 600

# 封面图建议尺寸
WECHAT_COVER_WIDTH = 900
WECHAT_COVER_HEIGHT = 383


# ---------------------------------------------------------------------------
# HTML 渲染
# ---------------------------------------------------------------------------

def render_wechat_html(content_ir: dict[str, Any]) -> str:
    """将 Content IR 渲染为公众号兼容的 HTML 正文。

    优先使用 Agent 分析的章节结构（chapters）和媒体信息（media_by_kind），
    在正文中按上下文位置正确插入图片。
    """
    parts: list[str] = []

    chapters = content_ir.get("flat_chapters") or content_ir.get("chapters") or []
    title = content_ir.get("title", "")
    subtitle = content_ir.get("subtitle", "")
    summary = content_ir.get("summary", "")

    # ---- 标题区 ----
    if title:
        parts.append(
            f'<section style="margin-bottom:24px;">'
            f'<h1 style="text-align:center;font-size:22px;font-weight:700;'
            f'color:#333;line-height:1.5;margin:0 0 8px;">'
            f'{html.escape(title)}</h1>'
        )
        if subtitle or summary:
            lead = subtitle or summary[:120]
            parts.append(
                f'<p style="text-align:center;color:#888;font-size:14px;'
                f'line-height:1.8;margin:0;">{html.escape(lead)}</p>'
            )
        parts.append("</section>")

    # ---- 章节正文 ----
    if chapters:
        for i, ch in enumerate(chapters):
            parts.append(_render_chapter_html(ch, is_first=(i == 0)))
    else:
        # 兜底：无章节时直接渲染原始正文
        body = content_ir.get("body", "")
        parts.append(_render_plain_body_html(body))

    # ---- 尾注 ----
    parts.append(
        '<section style="margin-top:32px;padding-top:16px;'
        'border-top:1px solid #e8e8e8;">'
        '<p style="color:#999;font-size:12px;text-align:center;">'
        '本内容由 Auto_Upt 生成</p>'
        '</section>'
    )

    return "\n".join(parts)


def _render_chapter_html(ch: dict[str, Any], is_first: bool = False) -> str:
    """渲染单个章节为 HTML。"""
    lines: list[str] = []
    level = ch.get("level", 1)
    heading = ch.get("title", "")
    content = ch.get("content", "")
    media_items = ch.get("media_items", [])

    # 章节标题
    tag = _heading_tag(level)
    margin = "margin-top:24px;" if not is_first else "margin-top:0;"
    lines.append(
        f'<section style="{margin}margin-bottom:12px;">'
        f'<{tag} style="font-size:{_heading_size(level)}px;font-weight:700;'
        f'color:#222;line-height:1.4;margin:0 0 10px;">'
        f'{html.escape(heading)}</{tag}>'
    )

    # 按位置将媒体插入正文
    if media_items and content:
        lines.extend(_render_content_with_media(content, media_items))
    elif content:
        lines.extend(_render_paragraphs_html(content))

    lines.append("</section>")

    # 递归子章节
    for sub in ch.get("sub_chapters", []):
        lines.append(_render_chapter_html(sub))

    return "\n".join(lines)


def _render_content_with_media(
    content: str,
    media_items: list[dict[str, Any]],
) -> list[str]:
    """将正文按段落分割，在适当位置插入媒体 HTML。

    策略：
    - 图片：如果有 surrounding_text 上下文，尝试在最近段落后插入。
    - 视频/音频：生成占位提示（公众号不支持直接嵌入）。
    """
    lines: list[str] = []
    paragraphs = [_strip_cn_media_markers(p.strip()) for p in content.split("\n")]
    paragraphs = [p for p in paragraphs if p.strip()]

    # 按 kind 分拣媒体
    images = [m for m in media_items if m.get("kind") == "image"]
    videos = [m for m in media_items if m.get("kind") == "video"]
    audios = [m for m in media_items if m.get("kind") == "audio"]

    # 简单策略：先渲染正文段落，图片插在中间/末尾
    img_idx = 0
    for i, para in enumerate(paragraphs):
        # 跳过已经是标题的段落
        if para.startswith(("#", "##", "###")):
            continue

        lines.append(
            f'<p style="color:#333;font-size:15px;line-height:2;'
            f'margin:0 0 12px;">{html.escape(para)}</p>'
        )

        # 插入图片：均匀分布
        if img_idx < len(images) and (i + 1) % max(1, len(paragraphs) // max(1, len(images))) == 0:
            lines.append(_render_image_html(images[img_idx]))
            img_idx += 1

    # 剩余图片插在末尾
    while img_idx < len(images):
        lines.append(_render_image_html(images[img_idx]))
        img_idx += 1

    # 视频/音频占位
    for v in videos:
        lines.append(_render_media_placeholder("视频", v))
    for a in audios:
        lines.append(_render_media_placeholder("音频", a))

    return lines


def _render_image_html(img: dict[str, Any]) -> str:
    """渲染单张图片的 HTML（公众号兼容格式）。

    使用 data-src 属性 + max-width:100% 实现响应式。
    即使 src 为空，也生成 <img> 标签，将文件名写入 data-src，
    以便发布时 adapter 能按文件名匹配本地素材并上传到微信。
    """
    src = img.get("src") or img.get("url") or ""
    name = img.get("name") or img.get("alt") or ""
    alt = html.escape(name or "图片")
    sizing = img.get("sizing") or {}
    width = sizing.get("width") or WECHAT_BODY_IMAGE_WIDTH

    style = (
        f"display:block;max-width:100%;width:{width}px;"
        f"margin:16px auto;border-radius:4px;"
    )

    # 当 src 为空但有文件名时，用文件名做 data-src，方便发布时匹配上传
    if not src:
        if name and ("." in name or name.strip()):
            src = name.strip()

    if not src:
        return (
            f'<p style="color:#999;font-size:13px;text-align:center;'
            f'padding:40px 0;background:#f5f5f5;margin:12px 0;">'
            f'📷 {alt}（待上传）</p>'
        )

    return (
        f'<img data-src="{html.escape(src)}" alt="{alt}" '
        f'style="{style}" />'
    )


def _render_media_placeholder(kind_cn: str, media: dict[str, Any]) -> str:
    """为公众号不支持的媒体类型生成占位提示。"""
    name = html.escape(media.get("name") or f"{kind_cn}文件")
    emoji = {"视频": "🎬", "音频": "🎵"}.get(kind_cn, "📎")
    return (
        f'<section style="text-align:center;padding:24px;'
        f'background:#f9f9f9;border-radius:6px;margin:12px 0;">'
        f'<p style="font-size:32px;margin:0 0 8px;">{emoji}</p>'
        f'<p style="color:#666;font-size:14px;margin:0;">'
        f'{kind_cn}：{name}</p>'
        f'<p style="color:#999;font-size:12px;margin:4px 0 0;">'
        f'公众号正文不支持直接嵌入{kind_cn}，请替换为外链或视频号卡片。</p>'
        f'</section>'
    )


def _strip_cn_media_markers(text: str) -> str:
    """移除正文中的中文媒体标记（【图片/视频/音频：xxx】），保留周围文本。"""
    if not text:
        return text
    # 先替换换行前的标记（标记单独成行），再替换行内标记
    cleaned = CN_MEDIA_MARKER_RE.sub("", text)
    # 清理可能留下的多余连续空行
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _render_paragraphs_html(content: str) -> list[str]:
    """将纯文本内容渲染为 HTML 段落。"""
    lines: list[str] = []
    for para in split_paragraphs(content):
        # 剥离中文媒体标记
        para = _strip_cn_media_markers(para).strip()
        if not para:
            continue
        # Markdown 标题 → HTML 标题
        if para.startswith("### "):
            lines.append(
                f'<h3 style="font-size:16px;font-weight:600;color:#333;'
                f'margin:16px 0 8px;">{html.escape(para[4:])}</h3>'
            )
        elif para.startswith("## "):
            lines.append(
                f'<h2 style="font-size:18px;font-weight:700;color:#222;'
                f'margin:20px 0 10px;">{html.escape(para[3:])}</h2>'
            )
        elif para.startswith("# "):
            lines.append(
                f'<h1 style="font-size:20px;font-weight:700;color:#111;'
                f'margin:24px 0 12px;">{html.escape(para[2:])}</h1>'
            )
        elif para.startswith("> "):
            lines.append(
                f'<blockquote style="border-left:3px solid #07c160;'
                f'padding:8px 12px;margin:12px 0;color:#666;font-size:14px;'
                f'background:#f0faf4;">{html.escape(para[2:])}</blockquote>'
            )
        elif para.startswith("- ") or para.startswith("* "):
            lines.append(
                f'<p style="color:#333;font-size:15px;line-height:2;'
                f'margin:0 0 4px 16px;">• {html.escape(para[2:])}</p>'
            )
        else:
            lines.append(
                f'<p style="color:#333;font-size:15px;line-height:2;'
                f'margin:0 0 12px;">{html.escape(para)}</p>'
            )
    return lines


def _render_plain_body_html(body: str) -> str:
    """兜底：直接渲染纯文本为 HTML 段落。"""
    paragraphs = _render_paragraphs_html(body)
    return (
        '<section style="margin-bottom:24px;">\n'
        + "\n".join(paragraphs)
        + "\n</section>"
    )


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def _heading_tag(level: int) -> str:
    if level <= 1:
        return "h2"
    elif level == 2:
        return "h3"
    return "h4"


def _heading_size(level: int) -> int:
    if level <= 1:
        return 19
    elif level == 2:
        return 17
    return 15


# ---------------------------------------------------------------------------
# 原有 render_draft（保持兼容）
# ---------------------------------------------------------------------------

def _asset_src(asset: dict[str, Any]) -> str:
    return asset.get("url") or asset.get("preview_url") or ""


def _external_media_block(kind: str, asset: dict[str, Any]) -> dict[str, Any]:
    label = "视频" if kind == "video" else "音频"
    return {
        "type": "unsupported_media",
        "media_type": kind,
        "text": f"公众号正文不支持直接嵌入{label}，请替换为外链或视频号卡片。",
        "src": _asset_src(asset),
        "alt": asset.get("name", f"{label}素材"),
        "asset_id": asset.get("id"),
        "mime_type": asset.get("mime_type"),
    }


def _pick_cover(assets: list[dict[str, Any]]) -> dict[str, Any] | None:
    for asset in assets:
        if asset.get("usage") in ("default_cover", "cover") and asset.get("type") in ("cover", "image"):
            return asset
    return next((asset for asset in assets if asset.get("type") in ("cover", "image")), None)


def render_draft(content_ir: dict[str, Any], profile: dict[str, Any]) -> dict[str, Any]:
    """生成公众号平台草稿（保留向后兼容）。

    新增：
    - wechat_html: WeChat API 兼容的 HTML 正文，可直接传入 draft/add 接口。
    - chapters: 来自 Agent 分析的章节数据（含媒体定位信息）。
    """
    limits = profile.get("limits", {})
    paragraphs = split_paragraphs(content_ir["body"])
    title = clip_text(
        first_non_empty(content_ir.get("title"), content_ir.get("summary")),
        limits.get("title_max_length", 64),
    )
    summary = content_ir.get("summary", "")
    body_blocks = content_ir.get("body_blocks", [])
    media_slots = content_ir.get("media_slots", {})
    chapters = content_ir.get("flat_chapters") or content_ir.get("chapters") or []

    # ---- 生成公众号 HTML ----
    wechat_html = render_wechat_html(content_ir)

    # ---- 传统文本正文 ----
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
        "body_blocks": body_blocks,
        "media_slots": media_slots,
        "rich_body": _build_rich_body(paragraphs, content_ir.get("assets", []), body_blocks),
        "cover_image": media_slots.get("cover") or _pick_cover(content_ir.get("assets", [])),
        "author": content_ir.get("author", "Auto_Upt"),
        "publish_date": content_ir.get("created_at", ""),
        # ---- 新增字段 ----
        "wechat_html": wechat_html,
        "chapters": chapters,
        "all_media": content_ir.get("all_media", []),
        "media_by_kind": content_ir.get("media_by_kind", {}),
        "style_notes": [
            "Use a clear intro before the main content.",
            "Keep paragraphs scannable for long-form reading.",
            "正文图片已内嵌为 HTML <img> 标签，封面需通过素材库上传。",
        ],
        "metadata": {
            "source_word_count": content_ir.get("word_count", 0),
            "estimated_read_time_minutes": max(1, content_ir.get("word_count", 0) // 500),
            "has_wechat_html": bool(wechat_html.strip()),
        },
    }


# ---------------------------------------------------------------------------
# 保留的辅助函数
# ---------------------------------------------------------------------------

def _text_to_rich_blocks(text: str) -> list[dict[str, Any]]:
    rich: list[dict[str, Any]] = []
    for para in split_paragraphs(text):
        if para.startswith("# "):
            rich.append({"type": "heading", "level": 1, "text": para[2:]})
        elif para.startswith("## "):
            rich.append({"type": "heading", "level": 2, "text": para[3:]})
        elif para.startswith("> "):
            rich.append({"type": "quote", "text": para[2:]})
        else:
            rich.append({"type": "paragraph", "text": para})
    return rich


def _build_rich_body(
    paragraphs: list[str],
    assets: list[dict[str, Any]],
    body_blocks: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if body_blocks:
        rich: list[dict[str, Any]] = []
        for block in body_blocks:
            if block.get("type") == "text":
                rich.extend(_text_to_rich_blocks(block.get("text", "")))
                continue
            asset = block.get("asset") or {}
            kind = block.get("asset_kind") or asset.get("type")
            if kind in {"video", "audio"}:
                rich.append(_external_media_block(kind, asset))
                continue
            rich.append(
                {
                    "type": kind,
                    "src": _asset_src(asset),
                    "alt": asset.get("name", ""),
                    "asset_id": asset.get("id"),
                    "mime_type": asset.get("mime_type"),
                }
            )
        return rich

    rich = []
    for para in paragraphs:
        rich.extend(_text_to_rich_blocks(para))

    for asset in assets:
        if asset.get("type") == "image" and asset.get("usage") not in ("default_cover", "cover"):
            rich.append({"type": "image", "src": _asset_src(asset), "alt": asset.get("name", "")})
        elif asset.get("type") in {"video", "audio"}:
            rich.append(_external_media_block(asset.get("type", "video"), asset))
    return rich
