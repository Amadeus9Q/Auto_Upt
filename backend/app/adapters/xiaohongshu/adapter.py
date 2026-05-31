from pathlib import Path
from typing import Any

from backend.app.adapters.base import PlatformAdapter, load_profile
from backend.app.adapters.clients import (
    LocalAsset,
    PlatformClientError,
    XiaohongshuMyaibotClient,
)
from backend.app.adapters.xiaohongshu.renderer import render_draft


class XiaohongshuAdapter(PlatformAdapter):
    def __init__(self) -> None:
        profile_path = Path(__file__).with_name("profile.yaml")
        super().__init__(load_profile(profile_path))

    def render(self, content_ir: dict[str, Any]) -> dict[str, Any]:
        return render_draft(content_ir, self.profile)

    async def publish(
        self,
        draft: dict[str, Any],
        account: dict[str, Any] | None = None,
        mode: str = "simulate",
    ) -> dict[str, Any]:
        if mode == "simulate":
            return self.simulate(draft)

        if account is None:
            raise PlatformClientError(
                "小红书发布需要提供 account 上下文（含 assets 列表）。",
                platform_code="ACCOUNT_REQUIRED",
                next_action="请确保发布请求中包含 asset_ids 信息。",
            )

        assets: list[LocalAsset] = account.get("assets", [])
        options = account.get("options", {})

        client = XiaohongshuMyaibotClient()

        # ---- 收集图片 URL ----
        image_urls: list[str] = []
        for asset in assets:
            if asset.asset_type == "image":
                url = self._public_url(asset)
                if url:
                    image_urls.append(url)

        # ---- 收集视频/封面 URL ----
        video_url: str | None = None
        cover_url: str | None = None
        for asset in assets:
            if asset.asset_type == "video":
                video_url = self._public_url(asset) or video_url
            if asset.purpose in {"cover", "xiaohongshu_cover", "default_cover"} and asset.asset_type == "image":
                cover_url = self._public_url(asset) or cover_url

        # ---- 标题 & 正文 ----
        title = options.get("title") or draft.get("title", "")
        content = options.get("content") or options.get("digest") or draft.get("summary") or draft.get("body", "")

        if not title.strip():
            raise PlatformClientError(
                "小红书发布需要标题。",
                platform_code="TITLE_REQUIRED",
                next_action="请在发布确认中填写标题。",
            )

        if not image_urls and not video_url:
            raise PlatformClientError(
                "小红书发布需要至少一张图片或一个视频。",
                platform_code="ASSETS_REQUIRED",
                next_action="请先在媒体库中上传图片或视频素材。",
            )

        # ---- 调用 myaibot API ----
        publish_result = await client.publish_note(
            title=title,
            content=content,
            images=image_urls if image_urls else None,
            video_url=video_url,
            cover_url=cover_url,
        )

        note_data = publish_result.get("data") or {}
        note_id = note_data.get("id") or ""
        qrcode = note_data.get("qrcode") or ""
        note_url = note_data.get("url") or ""

        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "mode": mode,
            "status": "succeeded",
            "external_id": note_id,
            "external_url": note_url,
            "external_status": "pending",
            "message": (
                "小红书笔记已提交。请扫描二维码在手机端完成发布。"
                if qrcode
                else "小红书笔记已提交。"
            ),
            "api_payload": {
                "title": title,
                "content": content[:200],
                "images_count": len(image_urls),
                "has_video": bool(video_url),
                "has_cover": bool(cover_url),
            },
            "raw_response": {
                "success": publish_result.get("success"),
                "data": {
                    "id": note_id,
                    "url": note_url,
                    "qrcode": qrcode,
                },
            },
            "qrcode": qrcode,
        }

    @staticmethod
    def _public_url(asset: LocalAsset) -> str:
        """返回素材的公网可访问 URL。"""
        from backend.app.core.config import get_settings

        settings = get_settings()
        public_base = settings.public_base_url.rstrip("/")
        return f"{public_base}/api/v1/assets/{asset.asset_id}/file"
