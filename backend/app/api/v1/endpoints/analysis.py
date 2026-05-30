"""内容分析 API —— 章节划分、媒体识别、平台文案生成。"""

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException

from backend.app.agents.content_analyst import ContentAnalystAgent
from backend.app.agents.platform_stylist import PlatformStylistAgent
from backend.app.schemas.analysis import (
    AgentAnalysisResponse,
    ContentAnalysis,
    PlatformCopy,
)
from backend.app.schemas.content import ContentInput, PlatformLiteral

router = APIRouter(prefix="/analysis", tags=["内容分析"])


@router.post(
    "/content",
    response_model=ContentAnalysis,
    summary="分析正文内容结构",
    description=(
        "功能：对正文进行深度分析，包括：\n"
        "- 章节划分与子标题提取（识别 Markdown h1/h2/h3 层级结构）\n"
        "- 图片、视频、音频的正确识别和分类\n"
        "- 正文摘要和字数的统计\n\n"
        "参数：请求体包含标题、正文、标签、素材列表和正文块。\n\n"
        "返回值：结构化分析结果（章节树、媒体列表、摘要等）。\n"
        "当前阶段使用规则引擎实现，不调用外部 AI 模型。"
    ),
    response_description="内容分析结果。",
)
async def analyze_content(
    request: Annotated[
        ContentInput,
        Body(description="待分析的正文内容。"),
    ],
) -> ContentAnalysis:
    agent = ContentAnalystAgent()
    try:
        return agent.analyze(
            body=request.body,
            title=request.title,
            tags=request.tags,
            content_blocks=[b.model_dump() for b in request.content_blocks] if request.content_blocks else None,
            assets=[a.model_dump() for a in request.assets],
            content_type=request.content_type,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"内容分析失败：{exc}") from exc


@router.post(
    "/platform-copy",
    response_model=dict[str, PlatformCopy],
    summary="生成多平台适配文案",
    description=(
        "功能：依据内容分析结果和用户选择的平台，生成对应平台的适配文案。\n\n"
        "支持的平台：wechat（公众号）、zhihu（知乎）、xiaohongshu（小红书）、bilibili（B站）。\n"
        "每个平台的文案包含：标题、结构化章节、纯文本正文、标签、媒体使用建议和风格提示。\n\n"
        "参数：\n"
        "- `analysis`：由 `/analysis/content` 返回的内容分析结果。\n"
        "- `platforms`：目标平台列表。为空时生成全部平台文案。\n\n"
        "返回值：按平台分组的 PlatformCopy。"
    ),
    response_description="按平台分组的结构化文案。",
)
async def generate_platform_copy(
    analysis: Annotated[
        ContentAnalysis,
        Body(description="内容分析结果（来自 /analysis/content）。"),
    ],
    platforms: Annotated[
        list[PlatformLiteral] | None,
        Body(description="目标平台列表，为空则生成全部。"),
    ] = None,
) -> dict[str, PlatformCopy]:
    agent = PlatformStylistAgent()
    try:
        return agent.generate(analysis=analysis, platforms=platforms)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"平台文案生成失败：{exc}") from exc


@router.post(
    "/full",
    response_model=AgentAnalysisResponse,
    summary="一键分析 + 生成多平台文案",
    description=(
        "功能：整合内容分析和平台文案生成，一次请求完成全部流程。\n\n"
        "参数：请求体包含标题、正文、标签、素材和目标平台列表。\n\n"
        "返回值：ContentAnalysis + 按平台分组的 PlatformCopy。"
    ),
    response_description="分析结果 + 平台文案。",
)
async def full_analysis(
    request: Annotated[
        ContentInput,
        Body(description="待分析的正文内容。"),
    ],
    platforms: Annotated[
        list[PlatformLiteral] | None,
        Body(description="目标平台列表，为空则生成全部。"),
    ] = None,
) -> AgentAnalysisResponse:
    content_agent = ContentAnalystAgent()
    stylist_agent = PlatformStylistAgent()
    try:
        analysis = content_agent.analyze(
            body=request.body,
            title=request.title,
            tags=request.tags,
            content_blocks=[b.model_dump() for b in request.content_blocks] if request.content_blocks else None,
            assets=[a.model_dump() for a in request.assets],
            content_type=request.content_type,
        )
        copies = stylist_agent.generate(analysis=analysis, platforms=platforms)
        return AgentAnalysisResponse(analysis=analysis, platform_copies=copies)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"全流程分析失败：{exc}") from exc
