from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Path

from backend.app.schemas.content import PlatformLiteral, PreviewCreateRequest, PreviewDraftUpdateRequest, PreviewResponse
from backend.app.services.preview_service import PreviewService


router = APIRouter(prefix="/previews", tags=["预览管理"])


@router.post(
    "",
    response_model=PreviewResponse,
    summary="创建预览（内存版，不落库）",
    description=(
        "功能：将用户输入内容标准化，调用指定平台适配器生成草稿和校验报告。"
        "预览数据仅在内存中计算，不写入数据库。\n\n"
        "参数：请求体包含内容输入字段和可选的 `platforms` 平台列表。"
        "`platforms` 为空时默认生成全部已支持平台预览。\n\n"
        "返回值：返回 `preview_id`、统一内容 IR、按平台分组的草稿、"
        "按平台分组的校验报告和创建时间。"
    ),
    response_description="多平台预览数据（内存版）。",
    responses={
        400: {"description": "请求中包含当前后端不支持的平台。"},
    },
)
async def create_preview(
    request: Annotated[
        PreviewCreateRequest,
        Body(description="需要生成预览的原始内容和平台列表。"),
    ],
) -> PreviewResponse:
    service = PreviewService()
    try:
        return service.create_preview_in_memory(request)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.patch(
    "/{preview_id}/drafts/{platform}",
    response_model=PreviewResponse,
    summary="校验平台草稿（内存版，不落库）",
    description=(
        "功能：接收前端对某个平台草稿文本框的修改，执行平台格式校验并返回校验报告。"
        "草稿数据不写入数据库，仅返回更新后的校验结果。\n\n"
        "参数：路径参数包含 `preview_id` 和 `platform`，请求体可传标题、正文、摘要或关键词。"
        "后端只会重新执行校验，不修改任何持久化数据。\n\n"
        "返回值：返回原样 `preview_id` 和 `content_ir`，只更新对应平台的 `drafts` 和 `validation_report`。"
    ),
    response_description="校验后的预览数据（内存版）。",
    responses={
        400: {"description": "请求中包含当前后端不支持的平台。"},
    },
)
async def update_preview_draft(
    preview_id: Annotated[str, Path(description="预览 ID（前端本地生成）。")],
    platform: Annotated[PlatformLiteral, Path(description="需要校验草稿的平台。")],
    request: Annotated[PreviewDraftUpdateRequest, Body(description="平台草稿局部更新参数。")],
) -> PreviewResponse:
    service = PreviewService()
    try:
        # 使用请求体中的草稿数据执行校验
        draft = {
            "title": request.title or "",
            "body": request.body or "",
            "summary": request.summary or "",
            "tags": request.tags or [],
        }
        validation = service.update_preview_draft_in_memory(draft, platform, request)
        return PreviewResponse(
            preview_id=preview_id,
            content_ir={},
            drafts={platform: draft},
            validation_report={platform: validation},
            created_at=None,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
