from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.schemas.account import (
    AccountPlatformResponse,
    AccountTestResponse,
    BilibiliCaptchaResponse,
    BilibiliLoginRequest,
    BilibiliLoginResponse,
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


# ── 微信公众号 ──────────────────────────────────────────────────────────


@router.post(
    "/wechat/connect",
    response_model=AccountPlatformResponse,
    summary="连接公众号账号",
    description=(
        "功能：保存微信公众号 AppID/AppSecret，并可在保存前测试 access_token 获取能力。\n\n"
        "参数：请求体包含 app_id、app_secret、display_name 和 test_connection。\n\n"
        "返回值：返回已连接公众号账号的状态、账号 ID、授权方式和平台能力。"
    ),
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


# ── B站密码登录 ─────────────────────────────────────────────────────────
# 具体路径必须在 /{platform} 通配路由之前注册，否则会被 /{platform} 匹配拦截。


@router.get(
    "/bilibili/login/captcha",
    response_model=BilibiliCaptchaResponse,
    summary="获取 B站登录验证码参数",
    description=(
        "功能：从 B站 passport 获取 Geetest 初始化参数，供前端加载极验组件。\n\n"
        "参数：无。\n\n"
        "返回值：返回 gt、challenge 和 token。前端完成极验后，将 challenge、validate、"
        "seccode 与 token 一起提交到密码登录接口。"
    ),
    response_description="B站 Geetest 初始化参数。",
    responses={400: {"description": "B站验证码接口返回异常或加密配置错误。"}},
)
async def get_bilibili_login_captcha() -> BilibiliCaptchaResponse:
    try:
        return await AccountService().get_bilibili_captcha()
    except (PlatformClientError, CredentialCryptoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/bilibili/login/password",
    response_model=BilibiliLoginResponse,
    summary="使用密码连接 B站账号",
    description=(
        "功能：接收 B站账号、密码和极验结果，后端获取 RSA 公钥加密密码，"
        "调用 B站 passport 登录并保存 Cookie 凭据。\n\n"
        "参数：请求体包含 username、password、token、challenge、validate、seccode，"
        "display_name 可选。\n\n"
        "返回值：登录成功后返回账号连接信息。后端只加密保存 SESSDATA、bili_jct、"
        "DedeUserID 等 Cookie，不保存明文密码。"
    ),
    response_description="B站账号连接结果。",
    responses={
        400: {
            "description": "账号密码错误、验证码失效、触发风控、B站接口返回错误或凭据加密失败。"
        }
    },
)
async def login_bilibili_with_password(
    request: Annotated[BilibiliLoginRequest, Body(description="B站密码登录参数。")],
    session: AsyncSession = Depends(get_session),
) -> BilibiliLoginResponse:
    try:
        return await AccountService(session).login_bilibili(request)
    except (PlatformClientError, CredentialCryptoError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ── 通用平台路由（/{platform} 通配必须在具体路径之后） ─────────────────


@router.get(
    "/{platform}",
    response_model=AccountPlatformResponse,
    summary="查询单个平台账号状态",
    description=(
        "功能：查询指定平台账号连接状态和平台能力。\n\n"
        "参数：路径参数 platform，例如 wechat 或 bilibili。\n\n"
        "返回值：返回平台账号状态、授权方式、真实发布支持情况和平台能力。"
    ),
    response_description="指定平台账号状态。",
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
    "/{platform}/test",
    response_model=AccountTestResponse,
    summary="测试平台账号连接",
    description=(
        "功能：测试指定平台最新连接账号的可用性。\n\n"
        "参数：路径参数 platform，例如 wechat 或 bilibili。\n\n"
        "返回值：公众号会尝试获取 access_token；B站会调用 nav 接口验证 Cookie 是否仍有效。"
    ),
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
    summary="断开账号连接",
    description=(
        "功能：删除已保存的账号连接和加密凭据。\n\n"
        "参数：路径参数 account_id，来自账号连接或登录接口返回值。\n\n"
        "返回值：返回被删除账号的最后状态，前端可据此刷新账号页面。"
    ),
    response_description="被删除账号的最后状态。",
    responses={404: {"description": "账号连接不存在。"}},
)
async def disconnect_account(
    platform: Annotated[str, Path(description="平台标识。")],
) -> dict[str, str]:
    service = AccountService()
    try:
        return service.disconnect(platform)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
