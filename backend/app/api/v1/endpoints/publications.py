from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.adapters.base import UnsupportedPublishModeError
from backend.app.adapters.clients import PlatformClientError
from backend.app.db.session import get_session
from backend.app.schemas.publication import PublicationDeleteResponse, PublicationPublishResponse, PublicationResponse
from backend.app.services.publish_service import PublishService


router = APIRouter(prefix="/publications", tags=["发布记录"])


@router.get(
    "/{publication_id}",
    response_model=PublicationResponse,
    summary="查询真实发布记录",
    description="查询公众号或 B站真实发布记录。",
    response_description="真实发布记录详情。",
    responses={404: {"description": "发布记录不存在。"}},
)
async def get_publication(
    publication_id: Annotated[str, Path(description="发布记录 ID。")],
    session: AsyncSession = Depends(get_session),
) -> PublicationResponse:
    service = PublishService(session)
    record = await service.get_publication(publication_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Publication not found.")
    return service.publication_to_response(record)


@router.post(
    "/{publication_id}/publish",
    response_model=PublicationPublishResponse,
    summary="将平台草稿提交发布",
    description=(
        "将已经创建的平台草稿继续提交发布。第二阶段仅公众号草稿支持该能力；"
        "接口会使用发布记录中保存的公众号草稿 media_id 调用微信提交发布接口。"
    ),
    response_description="草稿提交发布后的发布记录。",
    responses={
        400: {"description": "发布记录不是草稿，或当前平台不支持草稿转发布。"},
        404: {"description": "发布记录不存在。"},
    },
)
async def publish_draft_publication(
    publication_id: Annotated[str, Path(description="发布记录 ID。")],
    session: AsyncSession = Depends(get_session),
) -> PublicationPublishResponse:
    service = PublishService(session)
    try:
        result = await service.publish_draft_publication(publication_id)
    except (UnsupportedPublishModeError, PlatformClientError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if result is None:
        raise HTTPException(status_code=404, detail="Publication not found.")
    return result


@router.delete(
    "/{publication_id}",
    response_model=PublicationDeleteResponse,
    summary="删除真实发布记录",
    description="删除平台侧发布内容。第二阶段仅 B站支持删除测试稿件；公众号按平台能力返回不支持。",
    response_description="删除结果。",
    responses={404: {"description": "发布记录不存在。"}},
)
async def delete_publication(
    publication_id: Annotated[str, Path(description="发布记录 ID。")],
    session: AsyncSession = Depends(get_session),
) -> PublicationDeleteResponse:
    service = PublishService(session)
    result = await service.delete_publication(publication_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Publication not found.")
    return result
