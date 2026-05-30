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
    session: AsyncSession = Depends(get_session),
) -> AccountPlatformResponse:
    try:
        return await AccountService(session).get_account(platform)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/wechat/connect",
    response_model=AccountPlatformResponse,
    summary="连接公众号账号",
    description="保存微信公众号 AppID/AppSecret，并可在保存前测试 access_token 获取能力。",
    response_description="已连接的公众号账号状态。",
    responses={400: {"description": "凭据无效、加密配置错误或微信接口返回错误。"}},
)
async def connect_wechat(
    request: Annotated[WechatConnectRequest, Body(description="公众号连接参数。")],
    session: AsyncSession = Depends(get_session),
) -> AccountPlatformResponse:
    try:
        return await AccountService(session).connect_wechat(request)
    except (PlatformClientError, CredentialCryptoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/bilibili/oauth/start",
    response_model=BilibiliOAuthStartResponse,
    summary="发起 B站 OAuth 授权",
    description="生成 B站开放平台 OAuth 授权地址，前端应跳转到返回的 authorize_url。",
    response_description="B站 OAuth 授权地址和 state。",
    responses={400: {"description": "B站开放平台应用配置缺失或加密配置错误。"}},
)
async def start_bilibili_oauth() -> BilibiliOAuthStartResponse:
    try:
        return AccountService().start_bilibili_oauth()
    except (PlatformClientError, CredentialCryptoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/bilibili/oauth/callback",
    response_model=BilibiliOAuthCallbackResponse,
    summary="处理 B站 OAuth 回调",
    description="接收 B站 OAuth code/state，换取 token 并加密保存账号凭据。",
    response_description="授权成功后的 B站账号状态。",
    responses={400: {"description": "OAuth state 无效、code 换取失败或加密配置错误。"}},
)
async def handle_bilibili_oauth_callback(
    code: Annotated[str, Query(description="B站 OAuth 回调 code。")],
    state: Annotated[str, Query(description="后端生成的 OAuth state。")],
    session: AsyncSession = Depends(get_session),
) -> BilibiliOAuthCallbackResponse:
    try:
        return await AccountService(session).handle_bilibili_callback(code, state)
    except (PlatformClientError, CredentialCryptoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/{platform}/test",
    response_model=AccountTestResponse,
    summary="测试平台账号连接",
    description="测试指定平台最新连接账号的可用性。公众号会尝试获取 access_token，B站检查 token 状态。",
    response_description="账号连接测试结果。",
    responses={400: {"description": "请求的平台当前后端不支持。"}},
)
async def test_account(
    platform: Annotated[str, Path(description="平台标识。")],
    session: AsyncSession = Depends(get_session),
) -> AccountTestResponse:
    try:
        return await AccountService(session).test_account(platform)
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
