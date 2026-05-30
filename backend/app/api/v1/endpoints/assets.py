from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_session
from backend.app.schemas.asset import AssetListResponse, AssetResponse
from backend.app.services.asset_service import AssetService


router = APIRouter(prefix="/assets", tags=["素材管理"])


@router.post(
    "",
    response_model=AssetResponse,
    summary="上传发布素材",
    description="上传图片、封面、视频等素材到后端本地存储，发布任务通过返回的 asset_id 引用素材。",
    response_description="已保存的素材信息。",
)
async def upload_asset(
    file: Annotated[UploadFile, File(description="需要上传的素材文件。")],
    asset_type: Annotated[str, Form(description="素材类型：image、video 或 file。")] = "file",
    purpose: Annotated[str, Form(description="素材用途，例如 cover、body_image、video。")] = "content",
    session: AsyncSession = Depends(get_session),
) -> AssetResponse:
    service = AssetService(session)
    record = await service.create_asset(file, asset_type, purpose)
    return service.to_response(record)


@router.get(
    "",
    response_model=AssetListResponse,
    summary="查询素材列表",
    description="查询当前本地存储的发布素材。",
    response_description="素材列表。",
)
async def list_assets(
    session: AsyncSession = Depends(get_session),
) -> AssetListResponse:
    service = AssetService(session)
    records = await service.list_assets()
    return AssetListResponse(assets=[service.to_response(record) for record in records])


@router.get(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="查询素材详情",
    description="根据素材 ID 查询素材元信息。",
    response_description="素材详情。",
    responses={404: {"description": "素材不存在。"}},
)
async def get_asset(
    asset_id: Annotated[str, Path(description="素材 ID。")],
    session: AsyncSession = Depends(get_session),
) -> AssetResponse:
    service = AssetService(session)
    record = await service.get_asset(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return service.to_response(record)


@router.get(
    "/{asset_id}/download",
    summary="下载素材文件",
    description="下载指定素材文件，主要用于本地开发和前端预览。",
    responses={404: {"description": "素材不存在。"}},
)
async def download_asset(
    asset_id: Annotated[str, Path(description="素材 ID。")],
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    service = AssetService(session)
    record = await service.get_asset(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return FileResponse(
        record.file_path,
        media_type=record.content_type,
        filename=record.original_filename,
    )


@router.delete(
    "/{asset_id}",
    response_model=AssetResponse,
    summary="删除素材",
    description="删除素材记录和本地文件。",
    response_description="被删除的素材信息。",
    responses={404: {"description": "素材不存在。"}},
)
async def delete_asset(
    asset_id: Annotated[str, Path(description="素材 ID。")],
    session: AsyncSession = Depends(get_session),
) -> AssetResponse:
    service = AssetService(session)
    record = await service.delete_asset(asset_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Asset not found.")
    return service.to_response(record)
