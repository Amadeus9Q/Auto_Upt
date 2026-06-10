from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding

from backend.app.core.config import get_settings


class PlatformClientError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        platform_code: str | None = None,
        platform_message: str | None = None,
        retryable: bool = False,
        next_action: str = "请检查账号授权、平台参数和平台接口返回。",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.platform_code = platform_code
        self.platform_message = platform_message or message
        self.retryable = retryable
        self.next_action = next_action
        self.details = details or {}

    def to_result(self, platform: str) -> dict[str, Any]:
        return {
            "platform": platform,
            "status": "failed",
            "message": str(self),
            "platform_code": self.platform_code,
            "platform_message": self.platform_message,
            "retryable": self.retryable,
            "next_action": self.next_action,
            "details": self.details,
        }


@dataclass(slots=True)
class LocalAsset:
    asset_id: str
    asset_type: str
    purpose: str
    original_filename: str
    content_type: str
    file_path: str
    file_size: int
    sha256: str

    @property
    def path(self) -> Path:
        return Path(self.file_path)


class WechatOfficialAccountClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.wechat_api_base_url.rstrip("/")

    async def get_access_token(self, app_id: str, app_secret: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as client:
                response = await client.get(
                    "/cgi-bin/token",
                    params={
                        "grant_type": "client_credential",
                        "appid": app_id,
                        "secret": app_secret,
                    },
                )
        except httpx.HTTPError as exc:
            raise PlatformClientError(
                "微信 access_token 接口无法连接。",
                platform_code="NETWORK_ERROR",
                platform_message=str(exc),
                retryable=True,
                next_action="请确认当前网络或代理可以访问 api.weixin.qq.com，然后重试；也可以暂时关闭连接测试后保存凭据。",
                details={"error": str(exc)},
            ) from exc
        data = self._ensure_ok(response)
        return {
            "access_token": data["access_token"],
            "expires_in": data.get("expires_in", 7200),
            "raw": data,
        }

    async def upload_permanent_asset(
        self,
        access_token: str,
        asset: LocalAsset,
        material_type: str = "image",
    ) -> dict[str, Any]:
        with asset.path.open("rb") as asset_file:
            files = {
                "media": (
                    asset.original_filename,
                    asset_file,
                    asset.content_type or "application/octet-stream",
                )
            }
            async with httpx.AsyncClient(base_url=self.base_url, timeout=120) as client:
                response = await client.post(
                    "/cgi-bin/material/add_material",
                    params={"access_token": access_token, "type": material_type},
                    files=files,
                )
        return self._ensure_ok(response)

    async def upload_content_image(
        self,
        access_token: str,
        image_path: str | Path,
        filename: str = "image.png",
        content_type: str = "image/png",
    ) -> dict[str, Any]:
        """上传正文内图片（图文内容插图）。

        调用 POST /cgi-bin/media/uploadimg，返回 {"url": "..."} 可直接在 HTML
        <img> 标签中使用。与 upload_permanent_asset 不同，此接口专用于图文正文插图，
        不占用素材库配额，但图片仅能在图文消息中使用。
        """
        path = Path(image_path)
        with path.open("rb") as img_file:
            files = {
                "media": (
                    filename,
                    img_file,
                    content_type or "application/octet-stream",
                )
            }
            async with httpx.AsyncClient(base_url=self.base_url, timeout=60) as client:
                response = await client.post(
                    "/cgi-bin/media/uploadimg",
                    params={"access_token": access_token},
                    files=files,
                )
        return self._ensure_ok(response)

    async def add_draft(
        self,
        access_token: str,
        article: dict[str, Any],
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as client:
            response = await client.post(
                "/cgi-bin/draft/add",
                params={"access_token": access_token},
                json={"articles": [article]},
            )
        return self._ensure_ok(response)

    async def submit_publish(self, access_token: str, media_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as client:
            response = await client.post(
                "/cgi-bin/freepublish/submit",
                params={"access_token": access_token},
                json={"media_id": media_id},
            )
        return self._ensure_ok(response)

    async def get_publish_status(self, access_token: str, publish_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as client:
            response = await client.post(
                "/cgi-bin/freepublish/get",
                params={"access_token": access_token},
                json={"publish_id": publish_id},
            )
        return self._ensure_ok(response)

    @staticmethod
    def _ensure_ok(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise PlatformClientError(
                "WeChat returned a non-JSON response.",
                platform_code=str(response.status_code),
                retryable=response.status_code >= 500,
            ) from exc

        errcode = data.get("errcode", 0)
        if response.is_error or errcode not in (0, None):
            raise PlatformClientError(
                data.get("errmsg", "WeChat API request failed."),
                platform_code=str(errcode or response.status_code),
                platform_message=data.get("errmsg"),
                retryable=response.status_code >= 500 or errcode in {-1, 45009},
                details=data,
            )
        return data


class BilibiliWebClient:
    """B站 Web 登录和会员中心接口客户端。

    当前实现使用 B站 passport 登录流程获取 Cookie 凭据，不依赖开放平台
    Client ID/Secret。前端仍需负责 Geetest 组件交互，后端只接收校验结果。
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.passport_base = self.settings.bilibili_passport_base.rstrip("/")
        self.member_base = self.settings.bilibili_member_base.rstrip("/")
        self.api_base = self.settings.bilibili_api_base_url.rstrip("/")

    async def get_captcha(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(base_url=self.passport_base, timeout=30) as client:
                response = await client.get(
                    "/x/passport-login/captcha",
                    params={"source": "main_web"},
                    headers=self._browser_headers(),
                )
        except httpx.HTTPError as exc:
            raise self._network_error("B站验证码接口", exc) from exc
        data = self._ensure_ok(response)
        payload = data.get("data") or {}
        geetest = payload.get("geetest") or payload.get("result") or payload
        gt = geetest.get("gt")
        challenge = geetest.get("challenge")
        token = payload.get("token") or geetest.get("token")
        if not gt or not challenge or not token:
            raise PlatformClientError(
                "B站验证码接口没有返回完整的 gt/challenge/token。",
                platform_code="CAPTCHA_PAYLOAD_INVALID",
                retryable=True,
                next_action="请稍后重试获取验证码；如果持续失败，请检查 B站 passport 接口是否调整。",
                details=data,
            )
        return {
            "gt": gt,
            "challenge": challenge,
            "token": token,
            "raw": data,
        }

    async def get_web_key(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(base_url=self.passport_base, timeout=30) as client:
                response = await client.get(
                    "/x/passport-login/web/key",
                    headers=self._browser_headers(),
                )
        except httpx.HTTPError as exc:
            raise self._network_error("B站登录公钥接口", exc) from exc
        data = self._ensure_ok(response)
        payload = data.get("data") or {}
        public_key = payload.get("key") or payload.get("public_key")
        salt = payload.get("hash") or payload.get("salt")
        if not public_key or not salt:
            raise PlatformClientError(
                "B站登录公钥接口没有返回完整的 public key/hash。",
                platform_code="WEB_KEY_PAYLOAD_INVALID",
                retryable=True,
                next_action="请稍后重试登录；如果持续失败，请检查 B站 passport 接口是否调整。",
                details=data,
            )
        return {
            "public_key": public_key,
            "salt": salt,
            "raw": data,
        }

    @staticmethod
    def encrypt_password(password: str, public_key_pem: str, salt: str) -> str:
        key_text = public_key_pem.strip()
        if "BEGIN PUBLIC KEY" not in key_text:
            key_text = f"-----BEGIN PUBLIC KEY-----\n{key_text}\n-----END PUBLIC KEY-----"
        public_key = serialization.load_pem_public_key(key_text.encode("utf-8"))
        encrypted = public_key.encrypt(f"{salt}{password}".encode("utf-8"), padding.PKCS1v15())
        return base64.b64encode(encrypted).decode("utf-8")

    async def password_login(
        self,
        username: str,
        encrypted_password: str,
        token: str,
        challenge: str,
        validate: str,
        seccode: str,
    ) -> dict[str, Any]:
        payload = {
            "source": "main_web",
            "username": username,
            "password": encrypted_password,
            "keep": "true",
            "token": token,
            "challenge": challenge,
            "validate": validate,
            "seccode": seccode,
        }
        try:
            async with httpx.AsyncClient(base_url=self.passport_base, timeout=30) as client:
                response = await client.post(
                    "/x/passport-login/web/login",
                    data=payload,
                    headers=self._browser_headers(
                        {
                            "Origin": "https://passport.bilibili.com",
                            "Referer": "https://passport.bilibili.com/login",
                        }
                    ),
                )
        except httpx.HTTPError as exc:
            raise self._network_error("B站密码登录接口", exc) from exc
        data = self._ensure_ok(response)
        result = data.get("data") or {}
        status = result.get("status")
        if status in (2, "2"):
            raise PlatformClientError(
                "B站登录触发了风控或短信验证。",
                platform_code="RISK_CONTROL",
                platform_message=result.get("message") or "Risk control verification required.",
                retryable=False,
                next_action="请先在浏览器中登录 B站完成短信验证或风控校验，然后回到本工具重试。",
                details=self._redact_sensitive(data),
            )
        if status not in (None, 0, "0"):
            raise PlatformClientError(
                result.get("message") or "B站登录失败。",
                platform_code=str(status),
                platform_message=result.get("message"),
                retryable=False,
                next_action="请确认账号密码、极验验证码和账号状态后重试。",
                details=self._redact_sensitive(data),
            )

        cookies = self._extract_login_cookies(response, result)
        if not cookies.get("SESSDATA"):
            raise PlatformClientError(
                "B站登录成功响应中没有返回 SESSDATA。",
                platform_code="LOGIN_COOKIE_MISSING",
                retryable=False,
                next_action="请确认账号没有触发额外验证；必要时先在浏览器完成一次登录。",
                details=self._redact_sensitive(data),
            )
        return {
            "cookies": cookies,
            "raw_response": self._redact_sensitive(data),
        }

    async def nav_info(self, cookies: dict[str, str]) -> dict[str, Any]:
        self._ensure_cookie_credentials(cookies, require_csrf=False)
        try:
            async with httpx.AsyncClient(base_url=self.api_base, timeout=30) as client:
                response = await client.get(
                    "/x/web-interface/nav",
                    headers=self._cookie_headers(cookies),
                )
        except httpx.HTTPError as exc:
            raise self._network_error("B站账号状态接口", exc) from exc
        data = self._ensure_ok(response)
        nav_data = data.get("data") or {}
        if nav_data.get("isLogin") is False:
            raise PlatformClientError(
                "B站 Cookie 已失效或未登录。",
                platform_code="COOKIE_INVALID",
                retryable=False,
                next_action="请重新完成 B站登录。",
                details=self._redact_sensitive(data),
            )
        return data

    async def upload_video(self, cookies: dict[str, str], asset: LocalAsset) -> dict[str, Any]:
        self._ensure_cookie_credentials(cookies)
        preupload = await self._post_json(
            cookies,
            self.settings.bilibili_preupload_path,
            {
                "name": asset.original_filename,
                "size": asset.file_size,
                "r": "upos",
                "profile": "ugcupos/bup",
                "ssl": 0,
                "version": "2.14.0.0",
                "build": 0,
            },
        )
        data = preupload.get("data") or preupload
        endpoint = data.get("endpoint")
        upos_uri = data.get("upos_uri")
        auth = data.get("auth")

        if endpoint and upos_uri and auth:
            upload_result = await self._upload_upos(endpoint, upos_uri, auth, asset, data)
            return {
                "video_id": data.get("biz_id") or data.get("video_id") or data.get("upos_uri"),
                "data": data,
                "preupload_response": preupload,
                "upload_response": upload_result,
            }

        video_id = data.get("biz_id") or data.get("video_id") or data.get("upos_uri")
        if video_id:
            return {
                "video_id": video_id,
                "data": data,
                "preupload_response": preupload,
                "upload_response": None,
            }

        raise PlatformClientError(
            "B站预上传接口没有返回可用的视频上传地址。",
            platform_code="PREUPLOAD_PAYLOAD_INVALID",
            retryable=True,
            next_action="请检查 B站上传接口返回，或稍后重试。",
            details=preupload,
        )

    async def upload_cover(self, cookies: dict[str, str], asset: LocalAsset) -> dict[str, Any]:
        return await self._upload(cookies, self.settings.bilibili_cover_upload_path, asset)

    async def submit_video(
        self,
        cookies: dict[str, str],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._post_json(cookies, self.settings.bilibili_video_submit_path, payload)

    async def get_video_status(self, cookies: dict[str, str], external_id: str) -> dict[str, Any]:
        return await self._post_json(
            cookies,
            self.settings.bilibili_video_status_path,
            {"external_id": external_id},
        )

    async def delete_video(self, cookies: dict[str, str], external_id: str) -> dict[str, Any]:
        return await self._post_json(
            cookies,
            self.settings.bilibili_video_delete_path,
            {"external_id": external_id},
        )

    async def _post_json(
        self,
        cookies: dict[str, str],
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._ensure_cookie_credentials(cookies)
        request_payload = {
            **payload,
            "csrf": cookies["bili_jct"],
        }
        try:
            async with httpx.AsyncClient(base_url=self.member_base, timeout=60) as client:
                response = await client.post(
                    path,
                    headers=self._cookie_headers(cookies),
                    json=request_payload,
                )
        except httpx.HTTPError as exc:
            raise self._network_error("B站会员中心接口", exc) from exc
        return self._ensure_ok(response)

    async def _upload(self, cookies: dict[str, str], path: str, asset: LocalAsset) -> dict[str, Any]:
        self._ensure_cookie_credentials(cookies)
        with asset.path.open("rb") as asset_file:
            files = {
                "file": (
                    asset.original_filename,
                    asset_file,
                    asset.content_type or "application/octet-stream",
                )
            }
            try:
                async with httpx.AsyncClient(base_url=self.member_base, timeout=300) as client:
                    response = await client.post(
                        path,
                        headers=self._cookie_headers(cookies),
                        data={"csrf": cookies["bili_jct"]},
                        files=files,
                    )
            except httpx.HTTPError as exc:
                raise self._network_error("B站文件上传接口", exc) from exc
        return self._ensure_ok(response)

    async def _upload_upos(
        self,
        endpoint: str,
        upos_uri: str,
        auth: str,
        asset: LocalAsset,
        preupload_data: dict[str, Any],
    ) -> dict[str, Any]:
        endpoint_url = endpoint if endpoint.startswith(("http://", "https://")) else f"https://{endpoint}"
        upload_path = "/" + upos_uri.replace("upos://", "").lstrip("/")
        headers = {
            **self._browser_headers(),
            "X-Upos-Auth": auth,
        }
        try:
            async with httpx.AsyncClient(base_url=endpoint_url.rstrip("/"), timeout=600) as client:
                init_response = await client.post(
                    upload_path,
                    params={"uploads": "", "output": "json"},
                    headers=headers,
                )
                init_data = self._json_response(init_response)
                upload_id = init_data.get("upload_id") or init_data.get("uploadId")
                if not upload_id:
                    raise PlatformClientError(
                        "B站上传初始化没有返回 upload_id。",
                        platform_code="UPLOAD_INIT_INVALID",
                        retryable=True,
                        next_action="请检查 B站上传接口返回，或稍后重试。",
                        details=init_data,
                    )

                with asset.path.open("rb") as asset_file:
                    content = asset_file.read()
                upload_response = await client.put(
                    upload_path,
                    params={
                        "partNumber": 1,
                        "uploadId": upload_id,
                        "chunk": 0,
                        "chunks": 1,
                        "size": asset.file_size,
                        "start": 0,
                        "end": asset.file_size,
                        "total": asset.file_size,
                    },
                    headers={
                        **headers,
                        "Content-Type": "application/octet-stream",
                    },
                    content=content,
                )
                if upload_response.is_error:
                    raise PlatformClientError(
                        "B站视频分片上传失败。",
                        platform_code=str(upload_response.status_code),
                        retryable=upload_response.status_code >= 500,
                        next_action="请稍后重试上传，或检查素材文件大小和网络连接。",
                        details={"response_text": upload_response.text[:500]},
                    )

                complete_response = await client.post(
                    upload_path,
                    params={
                        "output": "json",
                        "name": asset.original_filename,
                        "profile": "ugcupos/bup",
                        "uploadId": upload_id,
                        "biz_id": preupload_data.get("biz_id"),
                    },
                    headers=headers,
                    json={"parts": [{"partNumber": 1, "eTag": "etag"}]},
                )
                complete_data = self._json_response(complete_response)
        except httpx.HTTPError as exc:
            raise self._network_error("B站视频上传接口", exc) from exc
        return {
            "init": init_data,
            "complete": complete_data,
            "upload_id": upload_id,
        }

    @staticmethod
    def _extract_login_cookies(response: httpx.Response, result: dict[str, Any]) -> dict[str, str]:
        cookie_names = ("SESSDATA", "bili_jct", "DedeUserID")
        cookies = {
            name: value
            for name in cookie_names
            if (value := response.cookies.get(name))
        }
        cookie_info = result.get("cookie_info") or {}
        for item in cookie_info.get("cookies", []):
            name = item.get("name")
            value = item.get("value")
            if name in cookie_names and value:
                cookies[name] = value
        return cookies

    @staticmethod
    def _cookie_header(cookies: dict[str, str]) -> str:
        return "; ".join(
            f"{key}={value}"
            for key, value in cookies.items()
            if key in {"SESSDATA", "bili_jct", "DedeUserID"} and value
        )

    def _cookie_headers(self, cookies: dict[str, str]) -> dict[str, str]:
        return {
            **self._browser_headers(),
            "Cookie": self._cookie_header(cookies),
        }

    @staticmethod
    def _browser_headers(extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
        }
        if extra:
            headers.update(extra)
        return headers

    @staticmethod
    def _ensure_cookie_credentials(cookies: dict[str, str], *, require_csrf: bool = True) -> None:
        if not cookies.get("SESSDATA"):
            raise PlatformClientError(
                "缺少 B站 SESSDATA Cookie。",
                platform_code="COOKIE_MISSING",
                retryable=False,
                next_action="请重新完成 B站登录。",
            )
        if require_csrf and not cookies.get("bili_jct"):
            raise PlatformClientError(
                "缺少 B站 bili_jct Cookie，无法执行需要 CSRF 的接口。",
                platform_code="CSRF_COOKIE_MISSING",
                retryable=False,
                next_action="请重新完成 B站登录。",
            )

    def _ensure_ok(self, response: httpx.Response) -> dict[str, Any]:
        data = self._json_response(response)
        code = data.get("code", data.get("errcode", 0))
        if code not in (0, "0", None):
            raise self._to_platform_error(response, data)
        return data

    @staticmethod
    def _json_response(response: httpx.Response) -> dict[str, Any]:
        try:
            parsed = response.json()
        except ValueError as exc:
            raise PlatformClientError(
                "B站接口返回了非 JSON 响应。",
                platform_code=str(response.status_code),
                retryable=response.status_code >= 500,
            ) from exc
        if response.is_error:
            raise PlatformClientError(
                parsed.get("message") or parsed.get("msg") or "B站接口请求失败。",
                platform_code=str(response.status_code),
                platform_message=parsed.get("message") or parsed.get("msg"),
                retryable=response.status_code >= 500,
                details=parsed,
            )
        return parsed

    def _to_platform_error(self, response: httpx.Response, data: dict[str, Any]) -> PlatformClientError:
        code = data.get("code", data.get("errcode", response.status_code))
        message = data.get("message") or data.get("msg") or data.get("errmsg") or "B站接口请求失败。"
        code_text = str(code)
        lower_message = str(message).lower()

        if code_text in {"86090"} or "risk" in lower_message or "风控" in str(message):
            return PlatformClientError(
                "B站登录触发了风控或短信验证。",
                platform_code="RISK_CONTROL",
                platform_message=message,
                retryable=False,
                next_action="请先在浏览器中登录 B站完成短信验证或风控校验，然后回到本工具重试。",
                details=self._redact_sensitive(data),
            )
        if code_text in {"-105"} or "captcha" in lower_message or "验证码" in str(message) or "极验" in str(message):
            return PlatformClientError(
                "B站验证码已失效或校验失败。",
                platform_code="CAPTCHA_EXPIRED",
                platform_message=message,
                retryable=True,
                next_action="请重新获取验证码并完成极验验证。",
                details=self._redact_sensitive(data),
            )
        if code_text in {"-629"} or "密码" in str(message) or "password" in lower_message:
            return PlatformClientError(
                "B站账号或密码错误。",
                platform_code="WRONG_PASSWORD",
                platform_message=message,
                retryable=False,
                next_action="请确认 B站账号和密码后重新登录。",
                details=self._redact_sensitive(data),
            )

        return PlatformClientError(
            message,
            platform_code=code_text,
            platform_message=message,
            retryable=response.status_code >= 500,
            details=self._redact_sensitive(data),
        )

    @staticmethod
    def _network_error(api_name: str, exc: httpx.HTTPError) -> PlatformClientError:
        return PlatformClientError(
            f"{api_name}无法连接。",
            platform_code="NETWORK_ERROR",
            platform_message=str(exc),
            retryable=True,
            next_action="请确认当前网络或代理可以访问 passport.bilibili.com、api.bilibili.com 和 member.bilibili.com，然后重试。",
            details={"error": str(exc)},
        )

    @classmethod
    def _redact_sensitive(cls, value: Any) -> Any:
        if isinstance(value, dict):
            sensitive = {
                "SESSDATA",
                "bili_jct",
                "DedeUserID",
                "password",
                "access_token",
                "refresh_token",
            }
            return {
                key: ("***" if key in sensitive and item else cls._redact_sensitive(item))
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._redact_sensitive(item) for item in value]
        return value


class XiaohongshuMyaibotClient:
    """小红书发布 API 客户端（通过 myaibot.vip 代理）。

    通过 myaibot.vip 的 RESTful API 将笔记内容提交到小红书平台。
    系统生成二维码后，用户扫码即可在手机端完成发布。

    API 文档：https://www.myaibot.vip/docs/api
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.base_url = self.settings.xiaohongshu_api_base_url.rstrip("/")

    @property
    def api_key(self) -> str:
        return self.settings.xiaohongshu_api_key

    async def publish_note(
        self,
        *,
        title: str,
        content: str,
        images: list[str] | None = None,
        video_url: str | None = None,
        cover_url: str | None = None,
    ) -> dict[str, Any]:
        """提交笔记到小红书（使用 publish-with-upload 接口自动转存资源）。

        推荐使用此接口：自动将图片/视频链接转存为公开 URL，无需自行对接 OSS。
        """
        note_type = "video" if video_url else "normal"
        payload: dict[str, Any] = {
            "api_key": self.api_key,
            "type": note_type,
        }
        if title:
            payload["title"] = title
        if content:
            payload["content"] = content
        if note_type == "normal" and images:
            payload["images"] = images
        if note_type == "video" and video_url:
            payload["video"] = video_url
        if cover_url:
            payload["cover"] = cover_url

        async with httpx.AsyncClient(base_url=self.base_url, timeout=120) as client:
            response = await client.post(
                "/api/rednote/publish-with-upload",
                headers={"Content-Type": "application/json"},
                json=payload,
            )
        return self._ensure_ok(response)

    async def get_note_status(self, note_id: str) -> dict[str, Any]:
        """查询笔记发布状态。

        状态：uploading → pending → submitted
        """
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as client:
            response = await client.post(
                f"/api/rednote/{note_id}/status",
                headers={"Content-Type": "application/json"},
                json={"api_key": self.api_key},
            )
        return self._ensure_ok(response)

    @staticmethod
    def _ensure_ok(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise PlatformClientError(
                "小红书 API 返回了非 JSON 响应。",
                platform_code=str(response.status_code),
                retryable=response.status_code >= 500,
            ) from exc

        if not data.get("success"):
            error = data.get("error") or {}
            code = error.get("code") or "UNKNOWN_ERROR"
            message = error.get("message") or "小红书 API 请求失败。"
            retryable = code in {"RATE_LIMIT_EXCEEDED", "INTERNAL_ERROR"}
            raise PlatformClientError(
                message,
                platform_code=code,
                platform_message=message,
                retryable=retryable,
                next_action={
                    "INVALID_API_KEY": "请检查 .env 中 XIAOHONGSHU_API_KEY 是否正确。",
                    "INSUFFICIENT_BALANCE": "请在 myaibot.vip 用户中心充值调用次数。",
                    "VALIDATION_ERROR": "请检查笔记参数是否符合小红书平台要求。",
                    "RATE_LIMIT_EXCEEDED": "请求频率超限，请稍后重试。",
                }.get(code, "请查看小红书 API 返回详情。"),
                details=data,
            )
        return data
