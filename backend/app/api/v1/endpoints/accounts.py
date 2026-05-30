from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from backend.app.schemas.account import (
    AccountPlatformResponse,
    AccountTestResponse,
    OAuthStartResponse,
    WechatConnectRequest,
)
from backend.app.services.account_service import AccountService


router = APIRouter(prefix="/accounts", tags=["账号管理"])


@router.get(
    "",
    response_model=list[AccountPlatformResponse],
    summary="查询账号状态列表",
)
async def list_accounts() -> list[AccountPlatformResponse]:
    service = AccountService()
    return service.list_accounts()


@router.get(
    "/{platform}",
    response_model=AccountPlatformResponse,
    summary="查询单个平台账号状态",
    responses={400: {"description": "请求的平台当前后端不支持。"}},
)
async def get_account(
    platform: Annotated[str, Path(description="平台标识。")],
) -> AccountPlatformResponse:
    service = AccountService()
    try:
        return service.get_account(platform)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/wechat/connect",
    response_model=AccountPlatformResponse,
    summary="保存公众号账号配置",
)
async def connect_wechat(payload: WechatConnectRequest) -> AccountPlatformResponse:
    service = AccountService()
    return service.connect_wechat(payload)


@router.get(
    "/bilibili/oauth/start",
    response_model=OAuthStartResponse,
    summary="启动 B站 OAuth 授权",
)
async def start_bilibili_oauth() -> OAuthStartResponse:
    service = AccountService()
    return service.start_bilibili_oauth()


@router.get(
    "/bilibili/oauth/callback",
    response_model=OAuthStartResponse,
    summary="接收 B站 OAuth 回调",
)
async def bilibili_oauth_callback(
    code: Annotated[str | None, Query(description="B站 OAuth 授权码。")] = None,
    state: Annotated[str | None, Query(description="B站 OAuth state。")] = None,
) -> OAuthStartResponse:
    service = AccountService()
    return service.finish_bilibili_oauth_callback(code=code, state=state)


@router.post(
    "/{platform}/test",
    response_model=AccountTestResponse,
    summary="测试平台账号连接",
    responses={400: {"description": "请求的平台当前后端不支持。"}},
)
async def test_account_connection(
    platform: Annotated[str, Path(description="平台标识。")],
) -> AccountTestResponse:
    service = AccountService()
    try:
        return service.test_connection(platform)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/{platform}",
    response_model=dict[str, str],
    summary="断开平台账号连接",
    responses={400: {"description": "请求的平台当前后端不支持。"}},
)
async def disconnect_account(
    platform: Annotated[str, Path(description="平台标识。")],
) -> dict[str, str]:
    service = AccountService()
    try:
        return service.disconnect(platform)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
