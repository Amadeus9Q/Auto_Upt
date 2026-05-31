from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.core.config import get_settings
from backend.app.db.session import get_session
from backend.app.schemas.agent import (
    AgentAdaptPreviewRequest,
    AgentAdaptPreviewResponse,
    AgentRunRequest,
    AgentRunResponse,
    AgentToolListResponse,
)
from backend.app.services.agent_service import AgentService, PersistentAgentService

import httpx
import logging

logger = logging.getLogger(__name__)


router = APIRouter(prefix="/agent-runs", tags=["Agent 编排"])


@router.get(
    "/tools",
    response_model=AgentToolListResponse,
    summary="查询 Agent 可用工具",
    description="返回当前后端白名单允许 Agent 调用的内置 MCP 风格工具列表。发布类真实接口不会出现在该列表中。",
    response_description="Agent 工具列表。",
)
async def list_agent_tools(
    session: AsyncSession = Depends(get_session),
) -> AgentToolListResponse:
    service = PersistentAgentService(session)
    return service.list_tools()


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


@router.post(
    "/adapt-preview",
    response_model=AgentAdaptPreviewResponse,
    summary="执行 Agent 工具编排并生成可发布预览",
    description=(
        "功能：通过内置 MCP 风格工具编排完成内容标准化、标题关键词提取、风格改写、"
        "多平台草稿渲染、校验和合规检查。默认会保存 preview，返回 preview_id 可直接进入发布流程。\n\n"
        "参数：请求体继承内容输入字段，并增加目标平台、风格目标、改写强度、是否修改标题/关键词、"
        "LLM 使用策略和是否保存预览。传入 `preview_id` 时，会把本次生成的目标平台草稿合并写回既有预览。\n\n"
        "返回值：返回 Agent 运行 ID、工具调用轨迹、标题关键词建议、改写正文、多平台草稿、"
        "校验报告、合规报告和 recommendations。"
    ),
    response_description="Agent 工具编排结果。",
    responses={
        400: {"description": "请求中包含当前后端不支持的平台。"},
    },
)
async def create_adapt_preview_agent_run(
    request: Annotated[
        AgentAdaptPreviewRequest,
        Body(description="Agent 工具编排请求参数。"),
    ],
    session: AsyncSession = Depends(get_session),
) -> AgentAdaptPreviewResponse:
    service = PersistentAgentService(session)
    try:
        return await service.create_adapt_preview_run(request)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class LlmHealthResponse(BaseModel):
    configured: bool = Field(description="是否配置了 API key 和 model。")
    model: str = Field(description="配置的模型名称。")
    endpoint: str = Field(description="LLM API 端点。")
    reachable: bool = Field(default=False, description="LLM 端点是否可达。")
    message: str = Field(description="状态描述。")


@router.get(
    "/llm-health",
    response_model=LlmHealthResponse,
    summary="LLM 连通性健康检查",
    description="测试配置的 LLM API 端点连通性，返回配置状态和可达性。",
    response_description="LLM 健康检查结果。",
)
async def check_llm_health() -> LlmHealthResponse:
    settings = get_settings()
    has_key = bool(settings.openai_api_key)
    has_model = bool(settings.openai_model)

    if not has_key or not has_model:
        return LlmHealthResponse(
            configured=False,
            model=settings.openai_model or "(未配置)",
            endpoint=settings.openai_base_url,
            reachable=False,
            message="未配置 API key 或模型。Agent 优化将使用规则引擎。",
        )

    endpoint = f"{settings.openai_base_url.rstrip('/')}/chat/completions"
    try:
        with httpx.Client(timeout=10) as client:
            response = client.get(
                settings.openai_base_url.rstrip("/") + "/models",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            )
        if response.status_code == 200:
            return LlmHealthResponse(
                configured=True,
                model=settings.openai_model,
                endpoint=endpoint,
                reachable=True,
                message=f"LLM 连接正常：{settings.openai_model} @ {settings.openai_base_url}",
            )
        else:
            return LlmHealthResponse(
                configured=True,
                model=settings.openai_model,
                endpoint=endpoint,
                reachable=False,
                message=f"LLM 端点返回 HTTP {response.status_code}，请检查 API key 和端点地址。",
            )
    except httpx.TimeoutException:
        return LlmHealthResponse(
            configured=True,
            model=settings.openai_model,
            endpoint=endpoint,
            reachable=False,
            message=f"连接 LLM 端点超时：{settings.openai_base_url}",
        )
    except Exception as exc:
        logger.warning("LLM health check failed: %s", exc)
        return LlmHealthResponse(
            configured=True,
            model=settings.openai_model,
            endpoint=endpoint,
            reachable=False,
            message=f"连接 LLM 端点失败：{exc}",
        )


@router.get(
    "/{run_id}",
    response_model=AgentAdaptPreviewResponse,
    summary="查询 Agent 工具编排运行详情",
    description="根据 run_id 查询已经保存的 Agent 工具编排结果和工具调用轨迹。",
    response_description="Agent 运行详情。",
    responses={404: {"description": "Agent 运行记录不存在。"}},
)
async def get_adapt_preview_agent_run(
    run_id: Annotated[str, Path(description="Agent 运行 ID。")],
    session: AsyncSession = Depends(get_session),
) -> AgentAdaptPreviewResponse:
    service = PersistentAgentService(session)
    record = await service.get_adapt_preview_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Agent run not found.")
    return record
