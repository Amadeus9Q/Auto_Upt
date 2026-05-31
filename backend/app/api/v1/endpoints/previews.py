from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_session
from backend.app.schemas.content import (
    DraftUpdateRequest,
    DraftUpdateResponse,
    PreviewCreateRequest,
    PreviewResponse,
)
from backend.app.services.preview_service import PreviewService


router = APIRouter(prefix="/previews", tags=["预览管理"])


@router.post(
    "",
    response_model=PreviewResponse,
    summary="创建预览记录",
    description=(
        "功能：将用户输入内容标准化，调用指定平台适配器生成草稿和校验报告，"
        "并把预览结果保存到 PostgreSQL。\n\n"
        "参数：请求体包含内容输入字段和可选的 `platforms` 平台列表。"
        "`platforms` 为空时默认生成全部已支持平台预览。\n\n"
        "返回值：返回 `preview_id`、统一内容 IR、按平台分组的草稿、"
        "按平台分组的校验报告和创建时间。`preview_id` 可用于查询预览详情或创建模拟发布任务。"
    ),
    response_description="已保存的多平台预览记录。",
    responses={
        400: {"description": "请求中包含当前后端不支持的平台。"},
    },
)
async def create_preview(
    request: Annotated[
        PreviewCreateRequest,
        Body(description="需要保存为预览记录的原始内容和平台列表。"),
    ],
    session: AsyncSession = Depends(get_session),
) -> PreviewResponse:
    service = PreviewService(session)
    try:
        record = await service.create_preview(request)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return service.to_response(record)


@router.get(
    "/{preview_id}",
    response_model=PreviewResponse,
    summary="查询预览记录",
    description=(
        "功能：根据预览记录 ID 查询已经保存的多平台预览详情。\n\n"
        "参数：路径参数 `preview_id` 为创建预览时返回的预览记录 ID。\n\n"
        "返回值：返回该预览的统一内容 IR、平台草稿、校验报告和创建时间。"
        "如果记录不存在，返回 404。"
    ),
    response_description="指定预览记录的详情。",
    responses={
        404: {"description": "没有找到对应的预览记录。"},
    },
)
async def get_preview(
    preview_id: Annotated[str, Path(description="预览记录 ID。")],
    session: AsyncSession = Depends(get_session),
) -> PreviewResponse:
    service = PreviewService(session)
    record = await service.get_preview(preview_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Preview not found.")
    return service.to_response(record)


@router.put(
    "/{preview_id}/drafts/{platform}",
    response_model=DraftUpdateResponse,
    summary="编辑单个平台草稿",
    description=(
        "功能：更新预览记录中单个平台的标题、正文和标签，并重新执行平台校验。\n\n"
        "参数：路径参数 `preview_id` + `platform`，请求体字段均可选——不传则不更新。\n\n"
        "返回值：更新后的草稿内容和重新计算的校验报告。\n"
        "可用于前端在每个平台预览中独立编辑标题、正文和标签。"
    ),
    response_description="更新后的平台草稿与校验报告。",
    responses={
        404: {"description": "预览记录或平台草稿不存在。"},
    },
)
async def update_platform_draft(
    preview_id: Annotated[str, Path(description="预览记录 ID。")],
    platform: Annotated[str, Path(description="平台标识，如 wechat、zhihu、bilibili、xiaohongshu。")],
    request: Annotated[
        DraftUpdateRequest,
        Body(description="要更新的字段，所有字段均可选。"),
    ],
    session: AsyncSession = Depends(get_session),
) -> DraftUpdateResponse:
    service = PreviewService(session)
    result = await service.update_platform_draft(
        preview_id=preview_id,
        platform=platform,
        title=request.title,
        body=request.body,
        tags=request.tags,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Preview or platform draft not found.")
    draft, validation_report = result
    return DraftUpdateResponse(
        preview_id=preview_id,
        platform=platform,
        draft=draft,
        validation_report=validation_report,
    )
