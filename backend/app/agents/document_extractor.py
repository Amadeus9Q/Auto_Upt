"""
文档内容提取智能体 —— 从导入的 .md / .docx 文档中提取标题、正文、标签、媒体位置等结构化信息。

支持：
1. 纯规则提取（Markdown 解析）
2. LLM 深度提取（启动时自动回退到规则引擎）
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

EXTRACT_SYSTEM_PROMPT = """\
你是一个专业的文档结构化分析器。你的任务是从用户导入的文档中提取关键信息。

## 提取规则

1. **标题**：按以下优先级提取标题：
   - 优先识别元数据行：`标题：xxx`、`题目：xxx`、`文档标题：xxx`、`title: xxx` 等模式，其后的文本即为标题。
   - 如果没有元数据行，取文档开头的第一个 # 标题行。
   - 如果都没有，取正文首行非空文本作为标题。
   - 提取的标题应当**去除 "标题："、"题目：" 等前缀字样**。

2. **标签**：按以下优先级提取标签（3-8 个中文关键词）：
   - 优先识别元数据行：`标签：xxx,yyy`、`关键词：xxx yyy`、`关键字：xxx`、`tags: xxx` 等模式。
   - 标签可能以逗号、顿号、分号、空格分隔，需要拆分。
   - 如果没有元数据标签，根据正文内容自动生成 3-8 个中文关键词。
   - 标签不要带 `#` 前缀。

3. **正文**：保留完整正文，去除页眉页脚、目录、版本号等元数据。元数据行（标题：/标签：/作者：/日期：/摘要：等）从正文中移除。

4. **摘要**：若文档有 `摘要：xxx` 或 `简介：xxx` 元数据行则提取之；否则生成 100-200 字摘要。

5. **内容类型**：判断是 article（文章）、video（视频脚本）或 mixed（图文混合）。

6. **媒体**：列出文档中所有图片/视频/音频文件名及其出现位置序号（从 0 开始）。

## 输出格式

严格输出 JSON，不要包含 markdown 代码块标记：

{
  "title": "主标题（不含"标题："等前缀）",
  "tags": ["标签1", "标签2", "标签3"],
  "body": "完整正文（不含元数据行）",
  "summary": "内容摘要",
  "content_type": "article",
  "media": [
    {"index": 0, "name": "image1.png", "kind": "image", "description": "图片描述"},
    {"index": 1, "name": "chart.png", "kind": "image", "description": "数据图表"}
  ]
}"""

EXTRACT_USER_TEMPLATE = """请分析以下文档内容，提取结构化信息。

文档原始文本：

{raw_text}"""


# ---------------------------------------------------------------------------
# JSON 提取
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    match = _JSON_BLOCK_RE.search(text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ---------------------------------------------------------------------------
# 规则引擎 fallback
# ---------------------------------------------------------------------------

# 文档元数据字段识别模式
# 格式：(字段类型, 匹配正则, 取值组索引)
_FIELD_PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    # ── 标题类 ──
    ("title", re.compile(r"^[#\s]*(?:标题|题目|文档标题|文章标题|文档名称)[：:]\s*(.+)$"), 1),
    ("title", re.compile(r"^(?:title|Title)[：:]\s*(.+)$"), 1),
    # ── 标签/关键词类 ──
    ("tags", re.compile(r"^[#\s]*(?:标签|关键词|关键字|关键词标签|话题)[：:]\s*(.+)$"), 1),
    ("tags", re.compile(r"^(?:tags?|keywords?)[：:]\s*(.+)$", re.IGNORECASE), 1),
    # ── 摘要类 ──
    ("summary", re.compile(r"^[#\s]*(?:摘要|内容摘要|简介|概述|描述)[：:]\s*(.+)$"), 1),
    ("summary", re.compile(r"^(?:summary|abstract|description)[：:]\s*(.+)$", re.IGNORECASE), 1),
    # ── 作者类 ──
    ("author", re.compile(r"^[#\s]*(?:作者|作者名|原创作者|笔者|文)[：:]\s*(.+)$"), 1),
    # ── 日期类 ──
    ("date", re.compile(r"^[#\s]*(?:日期|发布时间|创建时间|日期时间)[：:]\s*(.+)$"), 1),
]


def _parse_metadata_lines(lines: list[str]) -> tuple[dict[str, Any], list[str]]:
    """扫描文档前部（通常前 30 行）识别元数据行，返回 (元数据字典, 剩余行列表)。

    元数据行会被从 body_lines 中移除，避免出现在正文中。
    """
    metadata: dict[str, Any] = {
        "title": "",
        "tags": [],
        "summary": "",
        "author": "",
        "date": "",
    }
    meta_line_indices: set[int] = set()
    scan_limit = min(len(lines), 30)

    for i in range(scan_limit):
        line = lines[i]
        for field_type, pattern, group_idx in _FIELD_PATTERNS:
            m = pattern.match(line)
            if not m:
                continue
            raw_val = m.group(group_idx).strip()
            if not raw_val:
                continue
            if field_type == "title":
                if not metadata["title"]:
                    metadata["title"] = raw_val
            elif field_type == "tags":
                # 支持 ,/、/;/空格 分隔
                tag_list = re.split(r"[、,;；\s]+", raw_val)
                tag_list = [t.strip().lstrip("#") for t in tag_list if t.strip()]
                if tag_list:
                    metadata["tags"].extend(tag_list)
            elif field_type == "summary":
                if not metadata["summary"]:
                    metadata["summary"] = raw_val
            elif field_type == "author":
                if not metadata["author"]:
                    metadata["author"] = raw_val
            elif field_type == "date":
                if not metadata["date"]:
                    metadata["date"] = raw_val
            meta_line_indices.add(i)
            break  # 一行只匹配一个模式

    # 去重标签保留顺序
    seen: set[str] = set()
    unique_tags: list[str] = []
    for t in metadata["tags"]:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique_tags.append(t)
    metadata["tags"] = unique_tags

    remaining = [line for i, line in enumerate(lines) if i not in meta_line_indices]
    return metadata, remaining


def _tag_split(raw: str) -> list[str]:
    """将标签字符串按常见分隔符拆分。"""
    parts = re.split(r"[、,;；\s]+", raw.strip())
    return [p.strip().lstrip("#") for p in parts if p.strip()]


def _rule_based_extract(raw_text: str) -> dict[str, Any]:
    """纯规则提取：元数据行 → Markdown 标题 → 正文 → 关键词。"""
    lines = raw_text.splitlines()

    # 第一步：识别文档元数据行（标题：/标签：/关键词：等）
    meta, remaining = _parse_metadata_lines(lines)
    rule_title = meta.get("title", "")
    rule_tags = meta.get("tags", [])
    rule_summary = meta.get("summary", "")
    rule_author = meta.get("author", "")
    rule_date = meta.get("date", "")

    # 第二步：从剩余行中提取 Markdown # 标题（仅当元数据未给标题时）
    title = rule_title
    body_lines: list[str] = []
    found_md_title = False
    for line in remaining:
        stripped = line.strip()
        if not title and not found_md_title and stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            found_md_title = True
            continue
        body_lines.append(line)

    body = "\n".join(body_lines).strip()
    if not title and body_lines:
        # 兜底：正文首行非空行
        for bl in body_lines:
            if bl.strip():
                title = bl.strip().lstrip("#").strip()
                break

    # 第三步：标签（元数据标签优先，否则从正文提取关键词）
    tags = rule_tags
    if not tags:
        chinese_words = re.findall(r"[\u4e00-\u9fa5]{2,6}", body)
        word_freq: dict[str, int] = {}
        stop_words = {"可以", "一个", "这个", "什么", "我们", "他们", "因为", "所以", "但是", "如果", "没有", "不是", "还有", "这些", "那些", "自己", "已经", "以及", "或者", "不过", "虽然", "然而", "因此", "于是", "就是", "的话", "不会", "不能", "不要", "可能", "只是", "还是"}
        for w in chinese_words:
            if w in stop_words:
                continue
            word_freq[w] = word_freq.get(w, 0) + 1
        tags = [w for w, _ in sorted(word_freq.items(), key=lambda x: -x[1])[:8]]

    # 摘要
    summary = rule_summary or body[:200].replace("\n", " ").strip()

    # 媒体提取：![...](...) Markdown 图片语法
    media: list[dict[str, Any]] = []
    img_pattern = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
    for i, m in enumerate(img_pattern.finditer(raw_text)):
        media.append({
            "index": i,
            "name": m.group(2).split("/")[-1] or f"image_{i+1}",
            "kind": "image",
            "description": m.group(1) or "",
        })

    return {
        "title": title or "未命名文档",
        "tags": tags,
        "body": body,
        "summary": summary,
        "content_type": "article",
        "media": media,
    }


# ---------------------------------------------------------------------------
# LLM 提取器
# ---------------------------------------------------------------------------

class DocumentExtractorAgent:
    """使用 LLM 从导入文档中提取结构化内容。"""

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        self._model = model
        self._api_key = api_key
        self._client: Any = None

    @property
    def available(self) -> bool:
        if self._api_key:
            return True
        try:
            from backend.app.core.config import get_settings
            return bool(get_settings().openai_api_key)
        except Exception:
            return False

    @property
    def model(self) -> str:
        if self._model:
            return self._model
        try:
            from backend.app.core.config import get_settings
            return get_settings().openai_model or "gpt-4o"
        except Exception:
            return "gpt-4o"

    def _get_client(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import openai
        except ImportError:
            raise RuntimeError("openai 包未安装。")
        if not self._api_key:
            try:
                from backend.app.core.config import get_settings
                self._api_key = get_settings().openai_api_key
            except Exception:
                pass
        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY 未配置。")
        base_url: str | None = None
        try:
            from backend.app.core.config import get_settings
            s = get_settings()
            if s.openai_base_url:
                base_url = s.openai_base_url
        except Exception:
            pass
        self._client = openai.OpenAI(api_key=self._api_key, base_url=base_url)
        return self._client

    def extract(self, raw_text: str) -> dict[str, Any]:
        """从文档原始文本中提取结构化内容。

        优先使用 LLM，失败时回退到规则引擎。
        """
        if not raw_text or not raw_text.strip():
            return _rule_based_extract(raw_text)

        if not self.available:
            logger.info("LLM 不可用，使用规则引擎提取。")
            return _rule_based_extract(raw_text)

        try:
            client = self._get_client()
            user_prompt = EXTRACT_USER_TEMPLATE.format(raw_text=raw_text)

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": EXTRACT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=min(max(4096, len(raw_text) // 2), 16000),
            )

            content = response.choices[0].message.content or ""
            parsed = _extract_json(content)
            if parsed is None:
                logger.warning("LLM 返回无法解析，回退规则引擎。原始: %.200s", content)
                return _rule_based_extract(raw_text)

            # 确保必要字段存在
            return {
                "title": parsed.get("title", ""),
                "tags": parsed.get("tags", []),
                "body": parsed.get("body", raw_text),
                "summary": parsed.get("summary", ""),
                "content_type": parsed.get("content_type", "article"),
                "media": parsed.get("media", []),
            }
        except Exception as exc:
            logger.warning("LLM 文档提取失败: %s，回退规则引擎。", exc)
            return _rule_based_extract(raw_text)
