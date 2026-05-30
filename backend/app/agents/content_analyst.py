"""
内容分析智能体 —— 章节划分、子标题提取、媒体（图片/视频/音频）识别。

当前阶段使用规则引擎实现，后续可替换为 LLM 调用。
设计的输出结构（ContentAnalysis）保持稳定，便于后续接入 AI 模型。
"""

from __future__ import annotations

import re
from typing import Any

from backend.app.schemas.analysis import (
    Chapter,
    ContentAnalysis,
    MediaItem,
    MediaKindLiteral,
)


class ContentAnalystAgent:
    """内容分析 Agent。

    职责：
    1. 解析正文 Markdown 结构，提取章节层级（h1/h2/h3）
    2. 识别正文中的图片、视频、音频引用
    3. 生成结构化分析结果
    """

    # Markdown 标题正则：匹配 # / ## / ### 开头的行
    HEADING_PATTERN = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

    # ------------------------------------------------------------------
    # 纯文本备选标题识别正则（当正文不含 Markdown 标题时触发）
    # ------------------------------------------------------------------

    # 中文序号标题：一、二、三、... / （一）（二）/ ① ②
    CN_NUMBERED = re.compile(
        r"^[（(]?[一二三四五六七八九十百千]+[）)]?[、，,\s]",
    )

    # 阿拉伯数字序号：1. / 1.1 / 1- / 1)
    DIGIT_NUMBERED = re.compile(
        r"^(\d+[\.\-\)、]\s*)",
    )

    # 多级序号：1.1 / 2.3.1
    DOTTED_NUMBERED = re.compile(
        r"^(\d+(?:\.\d+)+)\s+",
    )

    # 章节标记：第X章 / 第X节 / Part X / Section X
    CHAPTER_MARKER = re.compile(
        r"^(第[一二三四五六七八九十百千\d]+[章节部分课]|Part\s+\d+|Section\s+\d+|Chapter\s+\d+|"
        r"【.+】|［.+］|\[.+\])",
        re.IGNORECASE,
    )

    # 全大写/英文标题行（如 "INTRODUCTION", "Background" 单独一行）
    EN_HEADING = re.compile(
        r"^[A-Z][A-Z\s\-]{3,60}$",
    )

    @staticmethod
    def _looks_like_heading(line: str, prev_blank: bool, next_blank: bool) -> tuple[bool, int]:
        """启发式判断一行文本是否像标题。

        规则：
        - 前后有空行（或位于文首/文尾），且行较短（≤60字）
        - 行末没有句号、逗号等正文标点
        - 不包含 URL 或媒体标记

        Returns:
            (is_heading, suggested_level): level 1/2/3
        """
        stripped = line.strip()
        if not stripped or len(stripped) > 60:
            return False, 0
        if re.search(r"https?://|!\[|\{\{asset:|【(?:图片|视频|音频)[：:]", stripped):
            return False, 0
        # 行末无常见正文标点 → 更像标题
        ends_clean = not re.search(r"[。，、；：！？\.\,\;\:\!\?]$", stripped)

        if not prev_blank and not next_blank:
            return False, 0

        # 长度 ≤ 30 → 可能是一级/二级标题; ≤ 15 → 更可能是一级
        if ends_clean or re.match(r"^[【\[［]", stripped):
            if len(stripped) <= 15 and prev_blank:
                return True, 1
            if len(stripped) <= 30:
                return True, 2
            return True, 3
        return False, 0

    # Markdown 图片语法：![alt](url)
    MD_IMAGE_PATTERN = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")

    # 段落级媒体标记：{{asset:image|video|audio:id}}
    ASSET_MARKER_PATTERN = re.compile(r"\{\{asset:(image|video|audio):([^}]+)\}\}")

    # 中文媒体标记：【图片：文件名.jpg】【视频：xxx.mp4】【音频：xxx.mp3】
    CN_MEDIA_MARKER = re.compile(r"【(图片|视频|音频)[：:]\s*([^】]+?)】")

    # 视频/音频 URL 模式（常见平台）
    MEDIA_URL_PATTERNS = {
        "video": re.compile(
            r"(https?://[^\s]*\.(?:mp4|mov|avi|webm|flv)(?:\?[^\s]*)?)",
            re.IGNORECASE,
        ),
        "audio": re.compile(
            r"(https?://[^\s]*\.(?:mp3|wav|ogg|flac|aac|m4a)(?:\?[^\s]*)?)",
            re.IGNORECASE,
        ),
        "image": re.compile(
            r"(https?://[^\s]*\.(?:png|jpg|jpeg|gif|webp|svg)(?:\?[^\s]*)?)",
            re.IGNORECASE,
        ),
    }

    def analyze(
        self,
        body: str,
        title: str | None = None,
        tags: list[str] | None = None,
        content_blocks: list[dict[str, Any]] | None = None,
        assets: list[dict[str, Any]] | None = None,
        content_type: str = "article",
    ) -> ContentAnalysis:
        """对正文执行完整分析。

        Args:
            body: 原始正文（Markdown / 纯文本）。
            title: 前端传入的标题，可为空。
            tags: 前端传入的标签列表。
            content_blocks: 前端传入的结构化正文块。
            assets: 前端上传的素材列表。
            content_type: 内容类型。

        Returns:
            ContentAnalysis: 结构化分析结果。
        """
        _tags = list(tags or [])
        _blocks = list(content_blocks or [])
        _assets = list(assets or [])

        # 1. 构建素材映射表
        asset_map: dict[str, dict[str, Any]] = {
            a.get("id", ""): a for a in _assets if a.get("id")
        }

        # 2. 提取 Markdown 图片
        md_media = self._extract_markdown_media(body)

        # 3. 提取正文中的 URL 媒体
        url_media = self._extract_url_media(body)

        # 4. 从 content_blocks 提取媒体
        block_media = self._extract_block_media(_blocks, asset_map)

        # 5. 从正文中的 {{asset:...}} 占位标记提取媒体
        marker_media = self._extract_asset_markers(body, asset_map)

        # 5b. 从正文中的 【图片/视频/音频：文件名】 中文标记提取媒体
        cn_media = self._extract_cn_media_markers(body, asset_map)

        # 6. 合并所有媒体（去重）
        all_media = self._merge_media(md_media, url_media, block_media, marker_media, cn_media)

        # 7. 按位置分配媒体到章节
        media_by_position = self._index_media_by_position(body, all_media)

        # 8. 章节划分
        chapters, flat_chapters = self._parse_chapters(body, media_by_position)

        # 9. 提取标题 & 副标题
        detected_title, subtitle = self._extract_title_and_subtitle(title, body, chapters)

        # 10. 生成摘要
        summary = self._generate_summary(body, chapters)

        # 11. 按类型分组媒体
        media_by_kind: dict[str, list[MediaItem]] = {"image": [], "video": [], "audio": []}
        for m in all_media:
            media_by_kind.setdefault(m.kind, []).append(m)

        return ContentAnalysis(
            title=detected_title,
            subtitle=subtitle,
            chapters=chapters,
            flat_chapters=flat_chapters,
            all_media=all_media,
            media_by_kind=media_by_kind,
            summary=summary,
            total_word_count=self._count_words(body),
            tags=_tags,
            content_type=content_type,
        )

    # ------------------------------------------------------------------
    # 章节解析
    # ------------------------------------------------------------------

    def _parse_chapters(
        self,
        body: str,
        media_by_position: dict[int, list[MediaItem]],
    ) -> tuple[list[Chapter], list[Chapter]]:
        """解析章节结构。

        策略（优先级）：
        1. Markdown 标题（# / ## / ###）—— 主方案
        2. 纯文本标题检测（序号、章节标记、启发式判断）—— 备选方案
        3. 全文作为单个默认章节 —— 兜底
        """
        headings = list(self.HEADING_PATTERN.finditer(body))

        if headings:
            return self._parse_markdown_chapters(body, headings, media_by_position)

        # 尝试纯文本标题检测
        plain_headings = self._detect_plain_headings(body)
        if plain_headings:
            return self._parse_plain_text_chapters(body, plain_headings, media_by_position)

        # 兜底：整篇作为单个默认章节
        chapter = self._build_chapter(
            level=1,
            title="正文",
            body=body,
            start_index=0,
            media_by_position=media_by_position,
        )
        return [chapter], [chapter]

    def _parse_markdown_chapters(
        self,
        body: str,
        headings: list[re.Match[str]],
        media_by_position: dict[int, list[MediaItem]],
    ) -> tuple[list[Chapter], list[Chapter]]:
        """解析 Markdown 标题结构，构建章节树。"""
        chapters: list[Chapter] = []
        flat: list[Chapter] = []
        stack: list[Chapter] = []

        for i, match in enumerate(headings):
            level = len(match.group(1))
            ch_title = match.group(2).strip()
            start = match.start()
            end = headings[i + 1].start() if i + 1 < len(headings) else len(body)

            content = body[start:end]
            content_lines = content.splitlines()
            ch_body = "\n".join(content_lines[1:]).strip() if content_lines else ""

            chapter = self._build_chapter(
                level=level,
                title=ch_title,
                body=ch_body,
                start_index=start,
                media_by_position=media_by_position,
            )

            while stack and stack[-1].level >= level:
                stack.pop()

            if not stack:
                chapters.append(chapter)
                stack = [chapter]
            else:
                stack[-1].sub_chapters.append(chapter)
                stack.append(chapter)

            flat.append(chapter)

        # 处理第一个标题之前的内容（导语/前言）
        first_heading_start = headings[0].start()
        preamble = body[:first_heading_start].strip()
        if preamble and chapters:
            chapters[0].content = preamble + "\n\n" + chapters[0].content

        return chapters, flat

    def _detect_plain_headings(self, body: str) -> list[dict[str, Any]]:
        """检测纯文本中的标题行。

        按优先级依次尝试多种规则，返回统一格式的标题信息列表：
        [{start, end, title, level}, ...]
        """
        lines = body.splitlines()
        total = len(lines)

        # 策略 A：中文序号（一、二、...）
        result = self._detect_numbered_headings(body, lines, total, self.CN_NUMBERED, "cn")
        if result:
            return result

        # 策略 B：章节标记（第X章、Part X、【标题】）—— 优先于纯数字序号
        result = self._detect_marker_headings(body, lines, total)
        if result:
            return result

        # 策略 C：多级数字序号（1.1 / 2.3.1）
        result = self._detect_numbered_headings(body, lines, total, self.DOTTED_NUMBERED, "dotted")
        if result:
            return result

        # 策略 D：阿拉伯数字序号（1. / 2） / 3)）
        result = self._detect_numbered_headings(body, lines, total, self.DIGIT_NUMBERED, "digit")
        if result:
            return result

        # 策略 E：启发式标题检测（短行 + 空行环绕）
        return self._detect_heuristic_headings(body, lines, total)

    def _detect_numbered_headings(
        self,
        body: str,
        lines: list[str],
        total: int,
        pattern: re.Pattern[str],
        style: str,
    ) -> list[dict[str, Any]]:
        """检测序号式标题（中文数字、阿拉伯数字、多级数字）。"""
        headings: list[dict[str, Any]] = []
        current_pos = 0
        last_level = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            match = pattern.match(stripped)
            if not match:
                current_pos += len(line) + 1
                continue

            # 排除过长行（更像正文而非标题）
            if len(stripped) > 50:
                current_pos += len(line) + 1
                continue

            prefix = match.group(1) if match.lastindex else match.group(0)
            title = stripped[match.end():].strip() or stripped

            # 推断层级
            if style == "dotted":
                depth = prefix.count(".") + 1
                level = min(depth, 3)
            elif style == "digit":
                # 纯数字（1.）是 level 2；前面有一、等则为 level 3
                level = 2
            else:
                level = 2

            headings.append({
                "start": current_pos,
                "end": current_pos + len(line),
                "title": title,
                "level": level,
            })
            current_pos += len(line) + 1

        return headings

    def _detect_marker_headings(
        self,
        body: str,
        lines: list[str],
        total: int,
    ) -> list[dict[str, Any]]:
        """检测章节标记式标题（第X章、Part X、【标题】）。"""
        headings: list[dict[str, Any]] = []
        current_pos = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            match = self.CHAPTER_MARKER.match(stripped)
            if not match:
                current_pos += len(line) + 1
                continue

            if len(stripped) > 50:
                current_pos += len(line) + 1
                continue

            # 排除媒体标记：【图片：xxx】【视频：xxx】【音频：xxx】
            if self.CN_MEDIA_MARKER.match(stripped):
                current_pos += len(line) + 1
                continue

            prefix = match.group(0)
            # 如果是【xxx】/［xxx］形式
            if prefix.startswith(("【", "［", "[")):
                level = 2
            else:
                level = 1  # 第X章 → 一级

            headings.append({
                "start": current_pos,
                "end": current_pos + len(line),
                "title": stripped,
                "level": level,
            })
            current_pos += len(line) + 1

        return headings

    def _detect_heuristic_headings(
        self,
        body: str,
        lines: list[str],
        total: int,
    ) -> list[dict[str, Any]]:
        """启发式检测：短行 + 空行环绕 ≈ 标题。"""
        headings: list[dict[str, Any]] = []
        current_pos = 0

        for i, line in enumerate(lines):
            prev_blank = i == 0 or lines[i - 1].strip() == ""
            next_blank = i == total - 1 or lines[i + 1].strip() == ""
            stripped = line.strip()

            is_heading, level = self._looks_like_heading(stripped, prev_blank, next_blank)
            if is_heading:
                headings.append({
                    "start": current_pos,
                    "end": current_pos + len(line),
                    "title": stripped,
                    "level": level,
                })

            current_pos += len(line) + 1

        # 过滤：如果识别出过多"标题"（超过 50%），说明正文格式不适合分段
        if headings and len(headings) > total * 0.5:
            return []

        return headings

    def _parse_plain_text_chapters(
        self,
        body: str,
        plain_headings: list[dict[str, Any]],
        media_by_position: dict[int, list[MediaItem]],
    ) -> tuple[list[Chapter], list[Chapter]]:
        """解析纯文本标题结构，构建章节树。"""
        chapters: list[Chapter] = []
        flat: list[Chapter] = []
        stack: list[Chapter] = []

        for i, h in enumerate(plain_headings):
            start = h["start"]
            end = h["end"]
            title = h["title"]
            level = h["level"]

            # 确定内容结束位置
            content_end = plain_headings[i + 1]["start"] if i + 1 < len(plain_headings) else len(body)
            ch_body = body[end:content_end].strip()

            chapter = self._build_chapter(
                level=level,
                title=title,
                body=ch_body,
                start_index=start,
                media_by_position=media_by_position,
            )

            while stack and stack[-1].level >= level:
                stack.pop()

            if not stack:
                chapters.append(chapter)
                stack = [chapter]
            else:
                stack[-1].sub_chapters.append(chapter)
                stack.append(chapter)

            flat.append(chapter)

        # 处理第一个标题前的导语
        first_start = plain_headings[0]["start"]
        preamble = body[:first_start].strip()
        if preamble and chapters:
            chapters[0].content = preamble + "\n\n" + chapters[0].content

        return chapters, flat

    def _build_chapter(
        self,
        level: int,
        title: str,
        body: str,
        start_index: int,
        media_by_position: dict[int, list[MediaItem]],
    ) -> Chapter:
        """构建单个章节对象。"""
        # 收集该章节范围内的媒体
        end_index = start_index + len(body) + len(title) + level + 1
        chapter_media: list[MediaItem] = []
        for pos, media_list in media_by_position.items():
            if start_index <= pos < end_index:
                chapter_media.extend(media_list)

        return Chapter(
            level=level,
            title=title,
            content=body,
            start_index=start_index,
            word_count=self._count_words(body),
            media_items=chapter_media,
        )

    # ------------------------------------------------------------------
    # 媒体识别
    # ------------------------------------------------------------------

    def _extract_markdown_media(self, body: str) -> list[MediaItem]:
        """从 Markdown 图片语法中提取媒体。"""
        media: list[MediaItem] = []
        for match in self.MD_IMAGE_PATTERN.finditer(body):
            media.append(
                MediaItem(
                    kind="image",
                    name=match.group(1) or "image",
                    src=match.group(2),
                    position=match.start(),
                    surrounding_text=self._get_surrounding_text(body, match.start(), match.end()),
                )
            )
        return media

    def _extract_url_media(self, body: str) -> list[MediaItem]:
        """从正文中的媒体 URL 识别图片/视频/音频。"""
        media: list[MediaItem] = []
        for kind, pattern in self.MEDIA_URL_PATTERNS.items():
            for match in pattern.finditer(body):
                url = match.group(1)
                # 避免重复：如果该 URL 已经在 markdown 语法中，跳过
                if f"]({url})" in body or f'"{url}"' in body:
                    continue
                media.append(
                    MediaItem(
                        kind=kind,  # type: ignore[arg-type]
                        name=url.rsplit("/", 1)[-1] if "/" in url else url,
                        src=url,
                        position=match.start(),
                        surrounding_text=self._get_surrounding_text(body, match.start(), match.end()),
                    )
                )
        return media

    def _extract_block_media(
        self,
        blocks: list[dict[str, Any]],
        asset_map: dict[str, dict[str, Any]],
    ) -> list[MediaItem]:
        """从 content_blocks 提取媒体信息。"""
        media: list[MediaItem] = []
        for i, block in enumerate(blocks):
            if block.get("type") != "asset":
                continue

            asset_id = block.get("asset_id", "")
            asset = asset_map.get(asset_id, {})
            kind: MediaKindLiteral = (
                block.get("asset_kind")
                or asset.get("type")
                or asset.get("asset_type")
                or "image"
            )
            # 标准化 kind 值
            if kind not in ("image", "video", "audio"):
                kind = "image"

            media.append(
                MediaItem(
                    asset_id=asset_id,
                    kind=kind,
                    name=asset.get("name") or asset.get("description"),
                    src=asset.get("url") or asset.get("preview_url"),
                    mime_type=asset.get("mime_type"),
                    role=self._normalize_role(block.get("role") or asset.get("usage")),
                    position=i,
                )
            )
        return media

    def _extract_asset_markers(
        self,
        body: str,
        asset_map: dict[str, dict[str, Any]],
    ) -> list[MediaItem]:
        """从正文中的 {{asset:kind:id}} 占位标记提取媒体。"""
        media: list[MediaItem] = []
        for match in self.ASSET_MARKER_PATTERN.finditer(body):
            kind: MediaKindLiteral = match.group(1)  # type: ignore[assignment]
            asset_id = match.group(2)
            asset = asset_map.get(asset_id, {})
            media.append(
                MediaItem(
                    asset_id=asset_id,
                    kind=kind,
                    name=asset.get("name") or f"{kind}-{asset_id}",
                    src=asset.get("url") or asset.get("preview_url"),
                    mime_type=asset.get("mime_type"),
                    role=self._normalize_role(asset.get("usage")),
                    position=match.start(),
                    surrounding_text=self._get_surrounding_text(body, match.start(), match.end()),
                )
            )
        return media

    # ------------------------------------------------------------------
    # 中文媒体标记：【图片：xxx.jpg】【视频：xxx.mp4】【音频：xxx.mp3】
    # ------------------------------------------------------------------

    # kind ← 中文映射
    CN_KIND_MAP: dict[str, str] = {"图片": "image", "视频": "video", "音频": "audio"}

    def _extract_cn_media_markers(
        self,
        body: str,
        asset_map: dict[str, dict[str, Any]],
    ) -> list[MediaItem]:
        """从正文中的 【图片/视频/音频：文件名】 标记提取媒体。

        匹配规则：
        1. 从正文中找到所有 【图片：xxx.jpg】 / 【视频：xxx.mp4】 / 【音频：xxx.mp3】
        2. 用文件名到素材库（asset_map）中匹配对应的素材条目
        3. 匹配策略（按优先级）：
           a. asset.name / original_filename 精确匹配
           b. asset.url 的 basename 匹配
           c. asset.name 包含该文件名（模糊匹配）
        4. 返回带完整素材信息的 MediaItem
        """
        media: list[MediaItem] = []
        for match in self.CN_MEDIA_MARKER.finditer(body):
            cn_kind = match.group(1)       # "图片" / "视频" / "音频"
            filename = match.group(2).strip()  # "294100_49.jpg"

            kind: MediaKindLiteral = self.CN_KIND_MAP.get(cn_kind, "image")  # type: ignore[assignment]

            # 按文件名查找匹配素材
            matched_asset = self._match_asset_by_filename(filename, asset_map)

            if matched_asset:
                asset_id = matched_asset.get("id", "")
                name = matched_asset.get("name") or matched_asset.get("original_filename") or filename
                src = matched_asset.get("url") or matched_asset.get("preview_url")
                mime_type = matched_asset.get("mime_type") or matched_asset.get("content_type")
                raw_usage = matched_asset.get("usage") or "inline"
                role = self._normalize_role(raw_usage)
            else:
                # 未匹配到素材：保留文件名作为 name，方便后续手动关联
                asset_id = ""
                name = filename
                src = None
                mime_type = None
                role = "inline"

            media.append(
                MediaItem(
                    asset_id=asset_id if asset_id else None,
                    kind=kind,
                    name=name,
                    src=src,
                    mime_type=mime_type,
                    role=role,
                    position=match.start(),
                    surrounding_text=self._get_surrounding_text(body, match.start(), match.end()),
                )
            )

        return media

    # 素材 usage → MediaItem role 映射
    _ROLE_MAP: dict[str, str] = {
        "cover": "cover", "default_cover": "cover",
        "body_image": "inline", "inline": "inline",
        "bilibili_video": "main", "main_video": "main",
    }

    @staticmethod
    def _normalize_role(raw_usage: str | None) -> str:
        """将素材的 usage 字段标准化为 MediaItem.role。"""
        if not raw_usage:
            return "inline"
        return ContentAnalystAgent._ROLE_MAP.get(raw_usage, "inline")

    @staticmethod
    def _match_asset_by_filename(
        filename: str,
        asset_map: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        """在素材库中按文件名查找匹配的素材条目。

        匹配优先级：
        1. asset.name / asset.original_filename 精确等于 filename
        2. asset.url 的 basename 等于 filename
        3. filename 包含在 asset.name 或 asset.original_filename 中（含扩展名或无扩展名）
        """
        if not filename or not asset_map:
            return None

        filename_lower = filename.lower()
        stem = filename.rsplit(".", 1)[0].lower() if "." in filename else filename_lower

        best: dict[str, Any] | None = None

        for asset in asset_map.values():
            name = (asset.get("name") or "").lower()
            orig = (asset.get("original_filename") or "").lower()
            url = (asset.get("url") or "").lower()

            # 精确匹配
            if name == filename_lower or orig == filename_lower:
                return asset

            # URL basename 匹配
            if url:
                url_basename = url.rsplit("/", 1)[-1].split("?")[0].lower()
                if url_basename == filename_lower:
                    return asset

            # 模糊匹配（stem 相同）
            if stem and (stem in name or stem in orig):
                if best is None:
                    best = asset

        return best

    def _merge_media(self, *sources: list[MediaItem]) -> list[MediaItem]:
        """合并多个来源的媒体并去重（按 src 去重）。"""
        seen: set[str] = set()
        merged: list[MediaItem] = []
        for source in sources:
            for item in source:
                key = item.src or item.asset_id or item.name or ""
                if key and key not in seen:
                    seen.add(key)
                    merged.append(item)
                elif not key:
                    merged.append(item)
        return merged

    def _index_media_by_position(
        self, body: str, media: list[MediaItem]
    ) -> dict[int, list[MediaItem]]:
        """将媒体按在正文中的位置索引分组。"""
        index: dict[int, list[MediaItem]] = {}
        for item in media:
            # 如果媒体有 URL，尝试在正文中定位
            pos = item.position
            if item.src and item.position == 0:
                found = body.find(item.src)
                if found >= 0:
                    pos = found
            index.setdefault(pos, []).append(item)
        return index

    def _get_surrounding_text(self, body: str, start: int, end: int, window: int = 80) -> str:
        """获取媒体前后的上下文文本。"""
        pre = body[max(0, start - window) : start].strip()
        post = body[end : end + window].strip()
        parts = []
        if pre:
            parts.append(pre[-window:])
        if post:
            parts.append(post[:window])
        return " … ".join(parts)

    # ------------------------------------------------------------------
    # 标题 & 摘要
    # ------------------------------------------------------------------

    def _extract_title_and_subtitle(
        self,
        explicit_title: str | None,
        body: str,
        chapters: list[Chapter],
    ) -> tuple[str | None, str | None]:
        """提取标题和副标题。

        优先级：
        1. 显式传入的标题
        2. 第一个 h1 标题
        3. 正文首行非空文本
        """
        title = explicit_title
        subtitle = None

        if not title and chapters:
            title = chapters[0].title
            # 如果有 h2 章节，第一个 h2 标题作为副标题
            if chapters[0].sub_chapters:
                subtitle = chapters[0].sub_chapters[0].title

        if not title:
            # 从正文首行获取
            for line in body.splitlines():
                candidate = line.strip().lstrip("#").strip()
                if candidate:
                    title = candidate[:80]
                    break

        if title is None:
            title = "Untitled"

        return title, subtitle

    def _generate_summary(self, body: str, chapters: list[Chapter]) -> str:
        """生成正文摘要。

        策略：
        1. 取第一个非空段落
        2. 如果只有一个章节，取章节内容的前 160 字
        """
        # 尝试取正文第一段
        for line in body.splitlines():
            candidate = line.strip().lstrip("#").strip()
            if candidate and not candidate.startswith("!["):
                return candidate[:160]

        # 回退到第一个章节
        if chapters:
            text = chapters[0].content.replace("\n", " ").strip()
            return text[:160]

        return body[:160]

    # ------------------------------------------------------------------
    # 工具方法
    # ------------------------------------------------------------------

    @staticmethod
    def _count_words(text: str) -> int:
        """统计字数（中文按字符数，英文按空格分词）。"""
        if not text:
            return 0
        # 中文字符计数
        chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        # 英文单词计数
        english_words = len([w for w in re.findall(r"[a-zA-Z]+", text)])
        return chinese_chars + english_words
