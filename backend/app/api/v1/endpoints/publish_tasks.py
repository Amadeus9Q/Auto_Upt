from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_session
from backend.app.schemas.content import PublishTaskCreateRequest, PublishTaskResponse
from backend.app.services.publish_service import PublishService


router = APIRouter(prefix="/publish-tasks", tags=["发布任务"])


@router.post(
    "",
    response_model=PublishTaskResponse,
    summary="创建模拟发布任务",
    description=(
        "功能：基于已经保存的预览记录，按指定平台执行模拟发布，并把发布任务保存到 PostgreSQL。\n\n"
        "参数：请求体包含 `preview_id`、发布模式 `mode` 和可选的 `platforms`。"
        "当前 MVP 仅支持 `mode=simulate`；`platforms` 为空时默认使用该预览记录中的全部平台草稿。\n\n"
        "返回值：返回任务 ID、关联预览 ID、任务状态、覆盖平台、按平台分组的模拟发布结果、"
        "错误信息和时间戳。如果预览记录不存在，返回 404；如果使用真实发布模式，返回 400。"
    ),
    response_description="已创建的模拟发布任务。",
    responses={
        400: {"description": "发布模式不是 simulate，或请求中包含不支持的平台。"},
        404: {"description": "没有找到对应的预览记录。"},
    },
)
async def create_publish_task(
    request: Annotated[
        PublishTaskCreateRequest,
        Body(description="模拟发布任务创建参数。"),
    ],
    session: AsyncSession = Depends(get_session),
) -> PublishTaskResponse:
    service = PublishService(session)
    try:
        record = await service.create_task(request)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if record is None:
        raise HTTPException(status_code=404, detail="Preview not found.")
    return service.to_response(record)


@router.get(
    "/{task_id}",
    response_model=PublishTaskResponse,
    summary="查询发布任务",
    description=(
        "功能：根据发布任务 ID 查询已经保存的模拟发布任务详情。\n\n"
        "参数：路径参数 `task_id` 为创建模拟发布任务时返回的任务 ID。\n\n"
        "返回值：返回任务状态、覆盖平台、按平台分组的模拟发布结果、错误信息和时间戳。"
        "如果任务不存在，返回 404。"
    ),
    response_description="指定模拟发布任务的详情。",
    responses={
        404: {"description": "没有找到对应的发布任务。"},
    },
)
async def get_publish_task(
    task_id: Annotated[str, Path(description="发布任务 ID。")],
    session: AsyncSession = Depends(get_session),
) -> PublishTaskResponse:
    service = PublishService(session)
    record = await service.get_task(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Publish task not found.")
    return service.to_response(record)
