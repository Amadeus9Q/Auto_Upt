from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

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
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as client:
            response = await client.get(
                "/cgi-bin/token",
                params={
                    "grant_type": "client_credential",
                    "appid": app_id,
                    "secret": app_secret,
                },
            )
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


class BilibiliOpenPlatformClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    def build_authorize_url(self, state: str) -> str:
        if not self.settings.bilibili_client_id:
            raise PlatformClientError(
                "BILIBILI_CLIENT_ID is not configured.",
                platform_code="CONFIG_MISSING",
                next_action="请先在 .env 中配置 B站开放平台应用信息。",
            )

        query = urlencode(
            {
                "client_id": self.settings.bilibili_client_id,
                "redirect_uri": self.settings.bilibili_redirect_uri,
                "response_type": "code",
                "state": state,
            }
        )
        return f"{self.settings.bilibili_authorize_url}?{query}"

    async def exchange_code(self, code: str) -> dict[str, Any]:
        payload = {
            "client_id": self.settings.bilibili_client_id,
            "client_secret": self.settings.bilibili_client_secret,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.settings.bilibili_redirect_uri,
        }
        return await self._post_form(self.settings.bilibili_token_url, payload)

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        payload = {
            "client_id": self.settings.bilibili_client_id,
            "client_secret": self.settings.bilibili_client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        return await self._post_form(self.settings.bilibili_refresh_token_url, payload)

    async def upload_video(self, access_token: str, asset: LocalAsset) -> dict[str, Any]:
        return await self._upload(access_token, self.settings.bilibili_video_upload_path, asset)

    async def upload_cover(self, access_token: str, asset: LocalAsset) -> dict[str, Any]:
        return await self._upload(access_token, self.settings.bilibili_cover_upload_path, asset)

    async def submit_video(
        self,
        access_token: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        return await self._post_json(access_token, self.settings.bilibili_video_submit_path, payload)

    async def get_video_status(self, access_token: str, external_id: str) -> dict[str, Any]:
        return await self._post_json(
            access_token,
            self.settings.bilibili_video_status_path,
            {"external_id": external_id},
        )

    async def delete_video(self, access_token: str, external_id: str) -> dict[str, Any]:
        return await self._post_json(
            access_token,
            self.settings.bilibili_video_delete_path,
            {"external_id": external_id},
        )

    async def _post_form(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        self._ensure_client_configured()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, data=payload)
        return self._ensure_ok(response)

    async def _post_json(
        self,
        access_token: str,
        path: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        self._ensure_client_configured()
        async with httpx.AsyncClient(base_url=self.settings.bilibili_api_base_url.rstrip("/"), timeout=60) as client:
            response = await client.post(
                path,
                headers={"Authorization": f"Bearer {access_token}"},
                json=payload,
            )
        return self._ensure_ok(response)

    async def _upload(self, access_token: str, path: str, asset: LocalAsset) -> dict[str, Any]:
        self._ensure_client_configured()
        with asset.path.open("rb") as asset_file:
            files = {
                "file": (
                    asset.original_filename,
                    asset_file,
                    asset.content_type or "application/octet-stream",
                )
            }
            async with httpx.AsyncClient(base_url=self.settings.bilibili_api_base_url.rstrip("/"), timeout=300) as client:
                response = await client.post(
                    path,
                    headers={"Authorization": f"Bearer {access_token}"},
                    files=files,
                )
        return self._ensure_ok(response)

    def _ensure_client_configured(self) -> None:
        missing = [
            name
            for name, value in (
                ("BILIBILI_CLIENT_ID", self.settings.bilibili_client_id),
                ("BILIBILI_CLIENT_SECRET", self.settings.bilibili_client_secret),
            )
            if not value
        ]
        if missing:
            raise PlatformClientError(
                f"Missing Bilibili Open Platform config: {', '.join(missing)}.",
                platform_code="CONFIG_MISSING",
                next_action="请先在 .env 中配置 B站开放平台应用信息。",
            )

    @staticmethod
    def _ensure_ok(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise PlatformClientError(
                "Bilibili returned a non-JSON response.",
                platform_code=str(response.status_code),
                retryable=response.status_code >= 500,
            ) from exc

        code = data.get("code", data.get("errcode", 0))
        if response.is_error or code not in (0, "0", None):
            raise PlatformClientError(
                data.get("message") or data.get("errmsg") or "Bilibili API request failed.",
                platform_code=str(code or response.status_code),
                platform_message=data.get("message") or data.get("errmsg"),
                retryable=response.status_code >= 500,
                details=data,
            )
        return data
