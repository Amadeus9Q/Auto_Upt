from typing import Annotated

from fastapi import APIRouter, Body, HTTPException

from backend.app.schemas.agent import AgentRunRequest, AgentRunResponse
from backend.app.services.agent_service import AgentService


router = APIRouter(prefix="/agent-runs", tags=["Agent 编排"])


@router.post(
    "/preview",
    response_model=AgentRunResponse,
    summary="执行模拟 Agent 预览编排",
    description=(
        "功能：按第一阶段路线图模拟执行多 Agent 内容发布编排，包括内容分析、平台风格规划、"
        "草稿渲染、格式校验、合规检查、模拟发布和恢复建议。\n\n"
        "参数：请求体包含标题、正文、内容类型、标签、素材、目标平台列表和是否执行模拟发布。"
        "`platforms` 为空时默认覆盖全部已支持平台。\n\n"
        "返回值：返回 `run_id`、编排步骤、统一内容 IR、平台草稿、校验报告、"
        "合规检查报告、模拟发布结果和下一步建议。当前接口不调用真实模型、不访问真实平台、不落库。"
    ),
    response_description="模拟 Agent 编排运行结果。",
    responses={
        400: {"description": "请求中包含当前后端不支持的平台。"},
    },
)
async def create_preview_agent_run(
    request: Annotated[
        AgentRunRequest,
        Body(description="模拟 Agent 编排请求参数。"),
    ],
) -> AgentRunResponse:
    service = AgentService()
    try:
        return service.create_preview_run(request)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
