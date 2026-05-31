"""
LLM 驱动的章节智能分析器 —— 语义分段 + 标题提取。

当正文不含 Markdown 标题时，调用 LLM 进行：
1. 逻辑章节切分（理解语义边界而非纯正则匹配）
2. 章节标题提取（优先复用文中已有措辞）
3. 全文标题/副标题/摘要生成

LLM 不可用或调用失败时返回 None，由 ContentAnalystAgent 回退到规则引擎。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from backend.app.schemas.analysis import Chapter, ContentAnalysis, MediaItem

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
你是一个专业的内容结构化分析师。你的任务是将用户提供的正文按逻辑语义切分为章节，并为每个章节提取标题。

## 核心规则

1. **优先复用文中标题**：如果正文中已有明显的标题行（如序号行"一、""1."、加粗短句、独立成行的主题句），直接使用原文措辞作为章节标题，不要改写。
2. **只在必要时生成**：仅当某个段落确实没有任何可用的标题文本时，才用简洁的语言（≤20字）生成一个。
3. **保持原文不变**：每个章节的 content 字段必须是原文的完整片段，不做任何改写或删减。
4. **合理分段**：章节数控制在 2-10 个。短文章（<200字）可以不拆分。
5. **识别层级**：level=1 为一级章节，level=2 为二级子章节，level=3 为三级。
6. **前言处理**：如果开头有导语/前言类内容，作为第一个章节，title 可用"前言"或从文中提取。

## 输出格式

严格输出 JSON，不要包含 markdown 代码块标记：

{
  "title": "全文主标题（可为空字符串）",
  "subtitle": "副标题或导语（可为空字符串）",
  "summary": "200 字以内的全文摘要",
  "chapters": [
    {
      "level": 1,
      "title": "章节标题（优先原文措辞）",
      "content": "该章节完整原文"
    }
  ]
}"""

USER_PROMPT_TEMPLATE = """请分析以下正文，进行章节划分和标题提取。

正文标题：{title}
正文内容：

{body}"""


# ---------------------------------------------------------------------------
# JSON 提取
# ---------------------------------------------------------------------------

_JSON_BLOCK_RE = re.compile(r"\{[\s\S]*\}")


def _extract_json(text: str) -> dict[str, Any] | None:
    """从 LLM 响应中提取 JSON 对象。"""
    # 尝试直接解析
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试找到最外层 {...}
    match = _JSON_BLOCK_RE.search(text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


# ---------------------------------------------------------------------------
# LLM 分析器
# ---------------------------------------------------------------------------


class LLMContentAnalyzer:
    """使用大语言模型进行智能章节划分与标题提取。

    调用方式：同步（使用 openai.OpenAI，非 AsyncOpenAI），
    保持与 ContentAnalystAgent 的同步接口兼容。
    """

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        """初始化 LLM 分析器。

        Args:
            model: 模型名，默认从 Settings.openai_model 读取。
            api_key: API 密钥，默认从 Settings.openai_api_key 读取。
        """
        self._model: str | None = model
        self._api_key: str | None = api_key
        self._client: Any = None  # openai.OpenAI 实例，延迟初始化

    # ------------------------------------------------------------------
    # 属性
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """LLM 是否可用（已配置 API key）。"""
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
        """延迟初始化 OpenAI 客户端。"""
        if self._client is not None:
            return self._client

        try:
            import openai
        except ImportError:
            raise RuntimeError(
                "openai 包未安装。请运行: pip install openai"
            )

        if not self._api_key:
            try:
                from backend.app.core.config import get_settings
                self._api_key = get_settings().openai_api_key
            except Exception:
                pass

        if not self._api_key:
            raise RuntimeError("OPENAI_API_KEY 未配置，无法使用 LLM 分析。")

        # 读取 base_url（支持 DeepSeek 等兼容接口）
        base_url: str | None = None
        try:
            from backend.app.core.config import get_settings
            settings = get_settings()
            if settings.openai_base_url:
                base_url = settings.openai_base_url
        except Exception:
            pass

        self._client = openai.OpenAI(api_key=self._api_key, base_url=base_url)
        return self._client

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def segment(
        self,
        body: str,
        title: str | None = None,
        content_type: str = "article",
        tags: list[str] | None = None,
    ) -> ContentAnalysis | None:
        """调用 LLM 对正文进行章节划分。

        Args:
            body: 原始正文。
            title: 前端传入标题。
            content_type: 内容类型。
            tags: 标签列表。

        Returns:
            ContentAnalysis 或 None（LLM 不可用/调用失败时返回 None）。
        """
        if not self.available:
            logger.info("LLM 不可用（未配置 API key），跳过。")
            return None

        if not body or not body.strip():
            return None

        try:
            raw = self._call_llm(body, title or "")
            parsed = _extract_json(raw)
            if parsed is None:
                logger.warning("LLM 返回内容无法解析为 JSON，原始响应: %.200s", raw)
                return None

            return self._build_analysis(parsed, body, tags or [], content_type)
        except Exception as exc:
            logger.warning("LLM 章节分析失败: %s，将回退到规则引擎。", exc)
            return None

    # ------------------------------------------------------------------
    # LLM 调用
    # ------------------------------------------------------------------

    def _call_llm(self, body: str, title: str) -> str:
        """调用 OpenAI Chat API，返回原始响应文本。"""
        client = self._get_client()
        user_prompt = USER_PROMPT_TEMPLATE.format(title=title or "无", body=body)

        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,  # 低温度保证输出稳定
            max_tokens=min(max(4096, len(body) // 2), 16000),
        )

        content = response.choices[0].message.content or ""
        return content

    # ------------------------------------------------------------------
    # 结果构建
    # ------------------------------------------------------------------

    def _build_analysis(
        self,
        parsed: dict[str, Any],
        body: str,
        tags: list[str],
        content_type: str,
    ) -> ContentAnalysis:
        """将 LLM 返回的 JSON 构建为 ContentAnalysis。"""
        raw_chapters: list[dict[str, Any]] = parsed.get("chapters", [])

        chapters: list[Chapter] = []
        flat_chapters: list[Chapter] = []

        for i, rc in enumerate(raw_chapters):
            level = max(1, min(3, int(rc.get("level", 1))))
            ch_title = str(rc.get("title", f"章节 {i + 1}")).strip()
            ch_content = str(rc.get("content", "")).strip()

            if not ch_content:
                continue

            ch = Chapter(
                level=level,
                title=ch_title,
                content=ch_content,
                start_index=body.find(ch_content) if ch_content in body else 0,
                word_count=self._count_words(ch_content),
                media_items=[],  # 媒体由 ContentAnalystAgent 后处理填充
                sub_chapters=[],
            )
            chapters.append(ch)
            flat_chapters.append(ch)

        # 全文标题：优先前端传入 > LLM 提取
        llm_title = str(parsed.get("title", "")).strip()
        llm_subtitle = str(parsed.get("subtitle", "")).strip()
        summary = str(parsed.get("summary", "")).strip()

        return ContentAnalysis(
            title=llm_title or None,
            subtitle=llm_subtitle or None,
            chapters=chapters,
            flat_chapters=flat_chapters,
            all_media=[],  # 由 ContentAnalystAgent 填充
            media_by_kind={},
            summary=summary,
            total_word_count=self._count_words(body),
            tags=tags,
            content_type=content_type,
        )

    @staticmethod
    def _count_words(text: str) -> int:
        """统计中文字数 + 英文词数。"""
        if not text:
            return 0
        # 中文字符
        cn = len(re.findall(r"[\u4e00-\u9fff]", text))
        # 英文单词
        en = len(re.findall(r"[a-zA-Z]+", text))
        return cn + en
