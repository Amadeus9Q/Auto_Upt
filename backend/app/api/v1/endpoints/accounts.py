from typing import Annotated

from fastapi import APIRouter, HTTPException, Path

from backend.app.schemas.account import AccountListResponse, AccountPlatformResponse
from backend.app.services.account_service import AccountService


router = APIRouter(prefix="/accounts", tags=["账号管理"])


@router.get(
    "",
    response_model=AccountListResponse,
    summary="查询账号占位状态",
    description=(
        "功能：为前端账号页面提供后端接口占位，返回当前支持平台的账号连接状态和后续授权方式。\n\n"
        "参数：无。\n\n"
        "返回值：返回每个平台的账号状态。第一阶段固定为 `not_configured`，"
        "不会读取真实账号、不会发起授权、不会调用真实平台。"
    ),
    response_description="平台账号占位状态列表。",
)
async def list_accounts() -> AccountListResponse:
    service = AccountService()
    return service.list_accounts()


@router.get(
    "/{platform}",
    response_model=AccountPlatformResponse,
    summary="查询单个平台账号占位状态",
    description=(
        "功能：查询指定平台的账号连接占位状态，供账号页面按平台展示。\n\n"
        "参数：路径参数 `platform` 为平台标识，例如 `wechat`、`zhihu`、"
        "`xiaohongshu` 或 `bilibili`。\n\n"
        "返回值：返回该平台账号状态、授权方式、平台能力和提示信息。"
        "如果平台不受支持，返回 400。"
    ),
    response_description="指定平台账号占位状态。",
    responses={
        400: {"description": "请求的平台当前后端不支持。"},
    },
)
async def get_account(
    platform: Annotated[str, Path(description="平台标识。")],
) -> AccountPlatformResponse:
    service = AccountService()
    try:
        return service.get_account(platform)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
