"""
平台文案生成智能体 —— 依据内容分析结果和平台特征，生成适配各平台的文案。

当前阶段使用规则模板引擎实现，后续可替换为 LLM 调用。
"""

from __future__ import annotations

import re
from typing import Any

from backend.app.schemas.analysis import (
    Chapter,
    ContentAnalysis,
    MediaItem,
    PlatformCopy,
)

# ---------------------------------------------------------------------------
# 平台风格配置
# ---------------------------------------------------------------------------

PLATFORM_STYLES: dict[str, dict[str, Any]] = {
    "wechat": {
        "display_name": "公众号",
        "tone": "保留原始风格，专业深度长文，结构化表达",
        "supported_media": ["image"],
        "template": "article",
        "structure_hint": "导语 + 正文（按章节展开）+ 结尾引导关注。尽量保留原文风格和结构。",
        "media_sizing": {
            "image": {
                "cover": {"width": 900, "height": 383, "ratio": "2.35:1", "note": "公众号封面图，建议 ≤2MB。"},
                "inline": {"width": 640, "height": 0, "note": "正文配图，宽度自适应，高度按比例。建议宽度 ≥600px。"},
            },
            "video": {
                "note": "公众号正文不支持直接嵌入视频，建议替换为视频号卡片。",
            },
            "audio": {
                "note": "公众号正文不支持直接嵌入音频，建议替换为音乐链接。",
            },
        },
        "style_notes": [
            "使用清晰的导语引导读者进入正文。",
            "每个章节之间可用分隔线或插图过渡。",
            "正文末尾添加引导关注或互动话术。",
            "避免过于营销化的用词，保持内容调性。",
        ],
    },
    "zhihu": {
        "display_name": "知乎",
        "tone": "专业严谨，理性深度知识分享",
        "supported_media": ["image"],
        "template": "article",
        "structure_hint": "引题 + 观点/结论 + 分点论证 + 总结。保持逻辑严密，引用数据和案例增强说服力。",
        "media_sizing": {
            "image": {
                "cover": {"width": 690, "height": 362, "ratio": "1.9:1", "note": "知乎封面图，建议 ≤5MB。"},
                "inline": {"width": 690, "height": 0, "note": "正文插图，最大宽度 690px，高度自适应。"},
            },
            "video": {
                "note": "知乎支持上传视频后插入，建议 16:9 横屏。",
            },
            "audio": {
                "note": "知乎不支持直接嵌入音频，建议转为文字或外链。",
            },
        },
        "style_notes": [
            "开头抛出一个引人思考的问题或观点。",
            "使用分点或列表增强可读性。",
            "引用文献或数据增强说服力。",
            "结尾给出结论或行动建议。",
        ],
    },
    "xiaohongshu": {
        "display_name": "小红书",
        "tone": "谈心式分享，亲切真诚，轻松种草风",
        "supported_media": ["image", "video"],
        "template": "social",
        "structure_hint": "标题 + 亮点展示 + 分段描述 + 标签 + 互动引导。用第一人称，像和朋友聊天。",
        "media_sizing": {
            "image": {
                "cover": {"width": 1080, "height": 1440, "ratio": "3:4", "note": "小红书封面图，推荐 3:4 竖版，≤20MB。"},
                "inline": {"width": 1080, "height": 0, "note": "正文配图建议 3:4 竖版比例，≤20MB。支持最多 18 张。"},
            },
            "video": {
                "note": "小红书支持视频，推荐 9:16 竖屏，时长 ≤15min。",
            },
            "audio": {
                "note": "小红书不支持纯音频，建议配图转为视频后发布。",
            },
        },
        "style_notes": [
            "标题要吸引眼球，使用 emoji 增强视觉。",
            "正文分段简短，每段不超过 3 行。",
            "善用表情符号和分隔符。",
            "标签要精准且覆盖热门话题。",
            "结尾引导点赞/收藏/评论。",
        ],
    },
    "bilibili": {
        "display_name": "B站",
        "tone": "轻松活泼，年轻化表达，适合视频内容社区",
        "supported_media": ["video", "image"],
        "template": "video",
        "structure_hint": "视频简介 + 内容要点（分点） + 标签 + 互动引导。语言轻松有趣，有网感。",
        "media_sizing": {
            "image": {
                "cover": {"width": 1146, "height": 717, "ratio": "16:10", "note": "B站视频封面，建议 ≤5MB。"},
                "inline": {"width": 0, "height": 0, "note": "B站简介不支持插入图片，可放外链图片 URL。"},
            },
            "video": {
                "note": "B站主视频建议 16:9 横屏，1080p+，≤8GB。",
            },
            "audio": {
                "note": "B站不支持纯音频，建议配图转为视频后上传。",
            },
        },
        "style_notes": [
            "标题要有搜索关键词。",
            "简介前 3 行是用户看到的预览，最重要信息放前面。",
            "使用简洁的分点列表描述内容要点。",
            "标签覆盖内容相关的热门搜索词。",
            "结尾引导一键三连。",
        ],
    },
}


class PlatformStylistAgent:
    """平台文案生成 Agent。

    职责：
    1. 接收 ContentAnalysis 分析结果
    2. 按平台特征生成适配文案
    3. 给出媒体使用建议
    """

    def generate(
        self,
        analysis: ContentAnalysis,
        platforms: list[str] | None = None,
    ) -> dict[str, PlatformCopy]:
        """为指定平台生成文案。

        Args:
            analysis: 内容分析结果。
            platforms: 目标平台列表。为空时生成全部平台。

        Returns:
            dict: 按平台标识分组的 PlatformCopy。
        """
        targets = platforms or list(PLATFORM_STYLES.keys())
        result: dict[str, PlatformCopy] = {}

        for platform in targets:
            style = PLATFORM_STYLES.get(platform)
            if not style:
                continue

            result[platform] = self._generate_for_platform(analysis, platform, style)

        return result

    # ------------------------------------------------------------------
    # 单平台生成
    # ------------------------------------------------------------------

    def _generate_for_platform(
        self,
        analysis: ContentAnalysis,
        platform: str,
        style: dict[str, Any],
    ) -> PlatformCopy:
        """为单个平台生成完整文案。"""
        template = style.get("template", "article")

        if template == "video":
            return self._generate_video_style(analysis, platform, style)
        elif template == "social":
            return self._generate_social_style(analysis, platform, style)
        else:
            return self._generate_article_style(analysis, platform, style)

    def _generate_article_style(
        self,
        analysis: ContentAnalysis,
        platform: str,
        style: dict[str, Any],
    ) -> PlatformCopy:
        """生成长文风格文案（公众号、知乎）。"""
        title = self._build_title(analysis, style)
        sections = self._build_sections(analysis, platform, style)
        plain_body = self._sections_to_plain(sections, style)
        tags = self._build_tags(analysis, style)
        media_recs = self._build_media_recommendations(analysis, platform, style)
        subtitle = analysis.subtitle or analysis.summary[:80]

        return PlatformCopy(
            platform=platform,
            display_name=style["display_name"],
            title=title,
            subtitle=subtitle,
            sections=sections,
            plain_body=plain_body,
            tags=tags,
            media_recommendations=media_recs,
            style_notes=list(style.get("style_notes", [])),
            metadata={
                "source_word_count": analysis.total_word_count,
                "template": style.get("template"),
                "tone": style.get("tone"),
            },
        )

    def _generate_video_style(
        self,
        analysis: ContentAnalysis,
        platform: str,
        style: dict[str, Any],
    ) -> PlatformCopy:
        """生成视频风格文案（B站）。"""
        title = self._build_title(analysis, style)
        sections = self._build_video_sections(analysis, style)
        plain_body = self._sections_to_plain(sections, style)
        tags = self._build_tags(analysis, style)
        media_recs = self._build_media_recommendations(analysis, platform, style)

        # B站特有：检查是否有视频素材
        has_video = bool(analysis.media_by_kind.get("video"))
        if not has_video:
            sections.insert(
                0,
                {
                    "heading": "📌 提示",
                    "paragraphs": ["该内容尚未关联视频素材，请在发布前上传视频文件。"],
                    "media_hints": [],
                    "platform_hints": ["B站发布需要至少一个视频文件。"],
                },
            )

        return PlatformCopy(
            platform=platform,
            display_name=style["display_name"],
            title=title,
            subtitle=analysis.summary[:120],
            sections=sections,
            plain_body=plain_body,
            tags=tags,
            media_recommendations=media_recs,
            style_notes=list(style.get("style_notes", [])),
            metadata={
                "source_word_count": analysis.total_word_count,
                "template": style.get("template"),
                "has_main_video": has_video,
            },
        )

    def _generate_social_style(
        self,
        analysis: ContentAnalysis,
        platform: str,
        style: dict[str, Any],
    ) -> PlatformCopy:
        """生成社交媒体风格文案（小红书）。"""
        title = self._build_title(analysis, style)
        sections = self._build_social_sections(analysis, style)
        plain_body = self._sections_to_plain(sections, style)
        tags = self._build_tags(analysis, style)
        media_recs = self._build_media_recommendations(analysis, platform, style)

        return PlatformCopy(
            platform=platform,
            display_name=style["display_name"],
            title=title,
            subtitle=None,
            sections=sections,
            plain_body=plain_body,
            tags=tags,
            media_recommendations=media_recs,
            style_notes=list(style.get("style_notes", [])),
            metadata={
                "source_word_count": analysis.total_word_count,
                "template": style.get("template"),
                "tone": style.get("tone"),
            },
        )

    # ------------------------------------------------------------------
    # 标题生成
    # ------------------------------------------------------------------

    def _build_title(self, analysis: ContentAnalysis, style: dict[str, Any]) -> str:
        """按平台风格生成标题。"""
        title = analysis.title or "Untitled"
        max_len = style.get("title_max_length", 60)
        platform = style.get("display_name", "")

        # 小红书：短标题 + emoji
        if style.get("template") == "social":
            if len(title) > 18:
                title = title[:17] + "…"
            # 如果没有 emoji 前缀，加一个
            if not any(ord(c) > 127 for c in title[:2]) or not self._has_emoji(title[:5]):
                pass  # 保持原标题，不强行加 emoji

        # 截断标题
        if len(title) > max_len:
            title = title[: max_len - 1] + "…"

        return title

    # ------------------------------------------------------------------
    # 章节内容构建
    # ------------------------------------------------------------------

    def _build_sections(
        self,
        analysis: ContentAnalysis,
        platform: str,
        style: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """构建长文风格的章节内容列表。"""
        sections: list[dict[str, Any]] = []

        # 导语
        if analysis.subtitle or analysis.summary:
            sections.append(
                {
                    "heading": "📖 导语" if platform == "wechat" else "引言",
                    "paragraphs": [analysis.subtitle or analysis.summary],
                    "media_hints": [],
                    "platform_hints": [],
                }
            )

        # 遍历章节
        for chapter in analysis.flat_chapters:
            media_hints: list[dict[str, Any]] = []
            for m in chapter.media_items:
                sizing = self._get_media_sizing(m.kind, m.role or "inline", style)
                hint = {
                    "asset_id": m.asset_id,
                    "kind": m.kind,
                    "name": m.name,
                    "src": m.src,
                    "action": self._media_action_for_platform(m.kind, platform),
                    "reason": self._media_reason(m.kind, platform),
                    "sizing": sizing,
                    "placement": {
                        "before_paragraph": 0,  # 插入在章节第 N 段之前（0 = 章节开头）
                        "context": m.surrounding_text,
                    },
                }
                media_hints.append(hint)

            # 分段落
            paragraphs = [p.strip() for p in chapter.content.split("\n") if p.strip()]
            if not paragraphs:
                paragraphs = [chapter.content]

            platform_hints: list[str] = []
            if platform == "wechat":
                platform_hints.append("可用分隔线或插图与上一节过渡。")
            elif platform == "zhihu":
                platform_hints.append("可在此处插入引用或数据支持。")

            sections.append(
                {
                    "heading": chapter.title,
                    "level": chapter.level,
                    "paragraphs": paragraphs,
                    "media_hints": media_hints,
                    "platform_hints": platform_hints,
                }
            )

        # 结尾引导
        if platform == "wechat":
            sections.append(
                {
                    "heading": "📢 关注我们",
                    "paragraphs": [
                        "如果觉得这篇文章对你有帮助，欢迎点赞、在看、转发支持我们！",
                        "关注「Auto_Upt」，获取更多优质内容。",
                    ],
                    "media_hints": [],
                    "platform_hints": ["此处可放置公众号二维码图片。"],
                }
            )
        elif platform == "zhihu":
            sections.append(
                {
                    "heading": "总结",
                    "paragraphs": [
                        "以上就是本次分享的全部内容。如果你有不同的看法或补充，欢迎在评论区留言讨论。",
                        "觉得有用的话，点个赞同让更多人看到～",
                    ],
                    "media_hints": [],
                    "platform_hints": [],
                }
            )

        return sections

    def _build_video_sections(
        self,
        analysis: ContentAnalysis,
        style: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """构建视频风格（B站）的章节内容列表。"""
        sections: list[dict[str, Any]] = []

        # 简介
        sections.append(
            {
                "heading": "视频简介",
                "paragraphs": [analysis.summary],
                "media_hints": [],
                "platform_hints": ["简介前3行是用户在搜索页看到的内容，务必包含关键词。"],
            }
        )

        # 内容要点（取章节标题为要点）
        if analysis.flat_chapters:
            points = []
            for ch in analysis.flat_chapters[:6]:
                points.append(f"• {ch.title}")
            sections.append(
                {
                    "heading": "内容要点",
                    "paragraphs": points,
                    "media_hints": [],
                    "platform_hints": [],
                }
            )

        # 时间戳（如果有多个章节）
        if len(analysis.flat_chapters) >= 2:
            timestamps = []
            for i, ch in enumerate(analysis.flat_chapters[:10]):
                minutes = i * 2
                ts = f"{minutes // 60:02d}:{minutes % 60:02d}  {ch.title}"
                timestamps.append(ts)
            sections.append(
                {
                    "heading": "时间轴",
                    "paragraphs": timestamps,
                    "media_hints": [],
                    "platform_hints": ["上传后可用 B站分P 或进度条标记功能。当前为预估时间。"],
                }
            )

        # 互动引导
        sections.append(
            {
                "heading": "🙏 求支持",
                "paragraphs": [
                    "如果这个视频对你有帮助，别忘了点赞、投币、收藏三连支持一下！",
                    "有什么想法欢迎在弹幕和评论区留言～",
                ],
                "media_hints": [],
                "platform_hints": [],
            }
        )

        return sections

    def _build_social_sections(
        self,
        analysis: ContentAnalysis,
        style: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """构建社交媒体风格（小红书）的章节内容列表。"""
        sections: list[dict[str, Any]] = []

        # 亮点提炼保持短句，但正文部分不再硬截断原文信息。
        highlights: list[str] = []
        for ch in analysis.flat_chapters[:4]:
            first_line = self._first_social_sentence(ch.content) or self._clean_social_line(ch.title)
            if first_line:
                highlights.append(f"✨ {self._clip_social_highlight(first_line)}")
        if not highlights:
            highlights.append(f"✨ {self._clip_social_highlight(analysis.summary)}")

        sections.append(
            {
                "heading": "🌟 亮点速览",
                "paragraphs": highlights,
                "media_hints": [],
                "platform_hints": ["每条亮点不超过一行，用 emoji 引导视线。"],
            }
        )

        # 详细内容保留完整章节，只做适合小红书阅读的短段落拆分。
        for chapter in analysis.flat_chapters:
            social_paragraphs: list[str] = []
            for p in chapter.content.split("\n"):
                social_paragraphs.extend(self._split_social_paragraph(p))

            media_hints = []
            for m in chapter.media_items:
                sizing = self._get_media_sizing(m.kind, m.role or "inline", style)
                action = self._media_action_for_platform(m.kind, "xiaohongshu")
                media_hints.append(
                    {
                        "asset_id": m.asset_id,
                        "kind": m.kind,
                        "name": m.name,
                        "src": m.src,
                        "action": action,
                        "reason": self._media_reason(m.kind, "xiaohongshu"),
                        "sizing": sizing,
                    }
                )

            if social_paragraphs or media_hints:
                sections.append(
                    {
                        "heading": self._clean_social_line(chapter.title),
                        "paragraphs": social_paragraphs,
                        "media_hints": media_hints,
                        "platform_hints": ["图片建议 3:4 竖版比例，可在正文中按段落穿插图片。"],
                    }
                )

        # 互动引导
        sections.append(
            {
                "heading": "💬 互动时间",
                "paragraphs": [
                    "觉得有用可以先收藏～",
                    "你更关注哪一部分？评论区聊聊。",
                ],
                "media_hints": [],
                "platform_hints": [],
            }
        )

        return sections

    @staticmethod
    def _clean_social_line(text: str) -> str:
        line = text.strip()
        line = re.sub(r"^\s*(?:[#>*\-+•]+\s*)+", "", line)
        line = re.sub(r"\s+", " ", line)
        return line.strip()

    @classmethod
    def _first_social_sentence(cls, text: str) -> str:
        for raw_line in text.splitlines():
            line = cls._clean_social_line(raw_line)
            if not line:
                continue
            if re.match(r"^!\[.*\]\(.*\)$", line) or line.startswith("{{asset:"):
                continue
            return line
        return ""

    @classmethod
    def _clip_social_highlight(cls, text: str, max_length: int = 56) -> str:
        line = cls._clean_social_line(text)
        if len(line) <= max_length:
            return line
        return line[: max_length - 1].rstrip() + "…"

    @classmethod
    def _split_social_paragraph(cls, text: str, max_length: int = 90) -> list[str]:
        paragraph = cls._clean_social_line(text)
        if not paragraph:
            return []

        parts: list[str] = []
        while len(paragraph) > max_length:
            candidates = [paragraph.rfind(mark, 0, max_length + 1) for mark in "。！？；;，,"]
            cut = max(candidates)
            if cut < max_length // 2:
                cut = max_length
            else:
                cut += 1
            parts.append(paragraph[:cut].strip())
            paragraph = paragraph[cut:].strip()

        if paragraph:
            parts.append(paragraph)
        return parts

    def _sections_to_plain(
        self, sections: list[dict[str, Any]], style: dict[str, Any]
    ) -> str:
        """将结构化章节展开为纯文本正文。"""
        lines: list[str] = []
        for sec in sections:
            heading = sec.get("heading", "")
            if heading:
                lines.append(heading)
            for p in sec.get("paragraphs", []):
                lines.append(p)
            lines.append("")  # 空行分隔
        body = "\n".join(lines).strip()
        max_len = style.get("body_max_length", 20000)
        if len(body) > max_len:
            body = body[: max_len - 3] + "..."
        return body

    # ------------------------------------------------------------------
    # 标签 & 媒体建议
    # ------------------------------------------------------------------

    def _build_tags(
        self, analysis: ContentAnalysis, style: dict[str, Any]
    ) -> list[str]:
        """按平台规则生成标签。"""
        import re as _re

        max_count = style.get("tags_max_count", 5)
        tags = list(analysis.tags[:max_count])

        # 如果标签不够，从章节标题中提取
        if len(tags) < max_count:
            for ch in analysis.flat_chapters:
                if len(tags) >= max_count:
                    break
                ch_tag = ch.title.strip()
                # 去除序号前缀（一、二、三 / 1. 2. 等）
                ch_tag = _re.sub(r"^[一二三四五六七八九十]+[、.．]\s*", "", ch_tag)
                ch_tag = _re.sub(r"^\d+[、.．]\s*", "", ch_tag)
                if ch_tag and ch_tag not in tags:
                    tags.append(ch_tag[:20])

        return tags[:max_count]

    def _build_media_recommendations(
        self,
        analysis: ContentAnalysis,
        platform: str,
        style: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """为平台的媒体使用提供建议。"""
        supported = style.get("supported_media", [])
        recommendations: list[dict[str, Any]] = []

        for m in analysis.all_media:
            action = "keep" if m.kind in supported else "skip"
            reason = (
                f"{style['display_name']}支持{m.kind}格式，可直接使用。"
                if m.kind in supported
                else f"{style['display_name']}不支持{m.kind}格式，建议替换为链接或静态图。"
            )
            sizing = self._get_media_sizing(m.kind, m.role or "inline", style)
            recommendations.append(
                {
                    "asset_id": m.asset_id,
                    "kind": m.kind,
                    "name": m.name,
                    "src": m.src,
                    "action": action,
                    "reason": reason,
                    "sizing": sizing,
                }
            )

        return recommendations

    @staticmethod
    def _media_action_for_platform(kind: str, platform: str) -> str:
        """判断某媒体类型在某平台的处理方式。"""
        platform_media_support = {
            "wechat": {"image": "keep", "video": "replace_with_link", "audio": "replace_with_link"},
            "zhihu": {"image": "keep", "video": "replace_with_link", "audio": "replace_with_link"},
            "xiaohongshu": {"image": "keep", "video": "keep", "audio": "skip"},
            "bilibili": {"image": "keep", "video": "keep", "audio": "skip"},
        }
        return platform_media_support.get(platform, {}).get(kind, "skip")

    @staticmethod
    def _get_media_sizing(kind: str, role: str, style: dict[str, Any]) -> dict[str, Any]:
        """获取某平台对某媒体类型的建议尺寸。

        Returns:
            dict: {width, height, ratio, note} 或仅 {note} 的提示信息。
        """
        media_sizing = style.get("media_sizing", {})
        kind_sizing = media_sizing.get(kind, {})
        if isinstance(kind_sizing, dict) and "note" in kind_sizing and "cover" not in kind_sizing:
            # 通用提示（如 video/audio 不支持的情况）
            return kind_sizing
        # 按 role（cover / inline）获取具体尺寸
        role_sizing = kind_sizing.get(role, kind_sizing.get("inline", {})) if isinstance(kind_sizing, dict) else {}
        return dict(role_sizing) if role_sizing else {"note": "请参考平台规范调整尺寸。"}

    @staticmethod
    def _media_reason(kind: str, platform: str) -> str:
        """生成媒体处理说明。"""
        reasons = {
            "wechat": {
                "image": "公众号支持图片，可直接在正文中插入。",
                "video": "公众号正文不支持直接嵌入视频，建议替换为视频号卡片或链接。",
                "audio": "公众号正文不支持直接嵌入音频，建议替换为音频链接或转为文字。",
            },
            "zhihu": {
                "image": "知乎支持图片插入，可直接使用。",
                "video": "知乎支持视频，可上传后插入。",
                "audio": "知乎不支持直接嵌入音频，建议转为文字或链接。",
            },
            "xiaohongshu": {
                "image": "小红书以图片为主，建议使用竖版 3:4 比例。",
                "video": "小红书支持视频，可直接使用。",
                "audio": "小红书不支持纯音频，建议配图转为视频。",
            },
            "bilibili": {
                "image": "B站支持在简介中插入图片链接，封面图可直接使用。",
                "video": "B站以视频为主体，请确保有主视频文件。",
                "audio": "B站不支持纯音频，建议配图转为视频。",
            },
        }
        return reasons.get(platform, {}).get(kind, "请检查平台规则。")

    @staticmethod
    def _has_emoji(text: str) -> bool:
        """检查文本是否包含 emoji。"""
        emoji_pattern = re.compile(
            "[\U0001F300-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF"
            "\U00002702-\U000027B0\U000024C2-\U0001F251\u2600-\u27BF\u2B50]"
        )
        return bool(emoji_pattern.search(text))
