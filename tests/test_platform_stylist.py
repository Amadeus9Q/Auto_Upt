from backend.app.agents.content_analyst import ContentAnalystAgent
from backend.app.agents.platform_stylist import PlatformStylistAgent


def test_xiaohongshu_rule_keeps_core_content_without_hard_truncation() -> None:
    body = """# AI 圈常见缩写快速入门

> 别再被这些缩写搞晕了，5分钟带你理清AI圈最热的五个概念。

## GPT：LLM 的标杆代表

GPT（Generative Pre-trained Transformer）是一类基于预训练和生成能力的大语言模型代表。

## LLM：大语言模型

LLM：大语言模型，AI的“大脑”，能够理解和生成自然语言内容。

## AI Agent：从回答问题到完成任务

AI Agent 能够围绕目标进行规划、调用工具，并根据执行结果继续调整下一步动作。
"""
    analysis = ContentAnalystAgent().analyze(
        body=body,
        title="AI 圈常见缩写快速入门",
        tags=["AI", "GPT", "LLM"],
        content_type="article",
    )

    copy = PlatformStylistAgent().generate(analysis, platforms=["xiaohongshu"])["xiaohongshu"]

    assert "Generative Pre-trained Transformer" in copy.plain_body
    assert "LLM：大语言模型" in copy.plain_body
    assert "AI Agent 能够围绕目标进行规划" in copy.plain_body
    assert "> 别再" not in copy.plain_body
    assert "Trans…" not in copy.plain_body


def test_xiaohongshu_rule_keeps_title_highlights_tags_and_long_body_complete() -> None:
    long_title = "小红书完整标题不应该被硬截断而是保留全部关键信息用于人工确认发布"
    long_tag = "超长关键词不应该被硬截断保留完整语义"
    chapters = []
    for index in range(1, 6):
        chapters.append(
            f"## 第{index}个章节标题\n"
            f"第{index}个章节的完整亮点句子需要保留下来，不能因为亮点速览只取前几项而丢失。"
        )
    long_tail = "这是一个超过默认正文长度限制后仍然需要保留的结尾标记"
    body = "# 小红书完整性测试\n\n" + "\n\n".join(chapters)
    body += "\n\n## 超长正文章节\n" + ("完整正文内容" * 4200) + long_tail

    analysis = ContentAnalystAgent().analyze(
        body=body,
        title=long_title,
        tags=[long_tag],
        content_type="article",
    )

    copy = PlatformStylistAgent().generate(analysis, platforms=["xiaohongshu"])["xiaohongshu"]
    highlight_text = "\n".join(copy.sections[0]["paragraphs"])

    assert copy.title == long_title
    assert long_tag in copy.tags
    assert "第5个章节的完整亮点句子需要保留下来" in highlight_text
    assert long_tail in copy.plain_body
    assert "…" not in copy.title
    assert "..." not in copy.plain_body
