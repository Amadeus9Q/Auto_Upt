from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.base import UnsupportedPublishModeError
from backend.app.db.session import get_session
from backend.app.schemas.content import PublishTaskCreateRequest, PublishTaskListResponse, PublishTaskResponse
from backend.app.services.publish_service import PublishService


router = APIRouter(prefix="/publish-tasks", tags=["发布任务"])


@router.get(
    "",
    response_model=PublishTaskListResponse,
    summary="查询发布任务列表",
    description=(
        "功能：从数据库查询已经创建的发布任务，用于前端刷新页面后恢复任务看板。\n\n"
        "参数：可选 `mode`、`status`、`platform` 和 `limit` 过滤任务；默认按创建时间倒序返回最近任务。\n\n"
        "返回值：返回 `tasks` 数组，每项结构与单个发布任务详情一致。"
    ),
    response_description="发布任务列表。",
)
async def list_publish_tasks(
    mode: Annotated[str | None, Query(description="按发布模式过滤：simulate、draft 或 publish。")] = None,
    status: Annotated[str | None, Query(description="按任务状态过滤：pending、running、succeeded 或 failed。")] = None,
    platform: Annotated[str | None, Query(description="按平台过滤：wechat、bilibili、zhihu 或 xiaohongshu。")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="返回任务数量上限。")] = 20,
    session: AsyncSession = Depends(get_session),
) -> PublishTaskListResponse:
    service = PublishService(session)
    records = await service.list_tasks(mode=mode, status=status, platform=platform, limit=limit)
    return PublishTaskListResponse(tasks=[service.to_response(record) for record in records])


@router.post(
    "",
    response_model=PublishTaskResponse,
    summary="创建发布任务",
    description=(
        "功能：基于已经保存的预览记录，按指定平台执行模拟发布或公众号/B站真实发布，并把发布任务保存到 PostgreSQL。\n\n"
        "参数：请求体包含 `preview_id`、发布模式 `mode` 和可选的 `platforms`。"
        "`simulate` 会同步完成；`draft/publish` 会创建真实发布任务并交给 Celery worker 执行。\n\n"
        "返回值：返回任务 ID、关联预览 ID、任务状态、覆盖平台、按平台分组的模拟发布结果、"
        "错误信息和时间戳。如果预览记录不存在，返回 404；如果平台或账号参数不符合真实发布要求，返回 400。"
    ),
    response_description="已创建的发布任务。",
    responses={
        400: {"description": "真实发布平台不支持，或缺少账号/素材参数。"},
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
    except (KeyError, UnsupportedPublishModeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if record is None:
        raise HTTPException(status_code=404, detail="Preview not found.")
    return service.to_response(record)


@router.post(
    "/{task_id}/refresh",
    response_model=PublishTaskResponse,
    summary="刷新真实发布任务状态",
    description="根据发布任务 ID 刷新公众号或 B站平台侧发布状态，并更新任务结果。",
    response_description="刷新后的发布任务详情。",
    responses={
        404: {"description": "没有找到对应的发布任务。"},
    },
)
async def refresh_publish_task(
    task_id: Annotated[str, Path(description="发布任务 ID。")],
    session: AsyncSession = Depends(get_session),
) -> PublishTaskResponse:
    service = PublishService(session)
    record = await service.refresh_task(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Publish task not found.")
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
