from pathlib import Path
from typing import Any

from backend.app.adapters.base import PlatformAdapter, load_profile
from backend.app.adapters.clients import BilibiliWebClient, LocalAsset, PlatformClientError
from backend.app.adapters.bilibili.renderer import render_draft


class BilibiliAdapter(PlatformAdapter):
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
                "Bilibili account credentials are required for real publish.",
                platform_code="ACCOUNT_REQUIRED",
                next_action="请先完成 B站登录，并在发布请求中传入 account_ids.bilibili。",
            )

        credentials = account.get("credentials", {})
        options = account.get("options", {})
        assets = account.get("assets", [])
        cookies = {
            key: value
            for key in ("SESSDATA", "bili_jct", "DedeUserID")
            if (value := credentials.get(key))
        }
        client = BilibiliWebClient()

        video_asset = self._find_asset(assets, options.get("video_asset_id"), "video")
        if video_asset is None:
            raise PlatformClientError(
                "Bilibili publish requires a video asset.",
                platform_code="VIDEO_REQUIRED",
                next_action="请先上传视频素材，并在 platform_options.bilibili.video_asset_id 或 asset_ids.bilibili 中传入。",
            )

        upload_result = await client.upload_video(cookies, video_asset)
        uploaded_video_id = upload_result.get("video_id") or upload_result.get("data", {}).get("video_id")

        cover_result: dict[str, Any] | None = None
        cover_asset = self._find_asset(assets, options.get("cover_asset_id"), "image")
        if cover_asset is not None:
            cover_result = await client.upload_cover(cookies, cover_asset)

        payload = {
            "title": options.get("title") or draft.get("title", ""),
            "description": options.get("description") or draft.get("body", ""),
            "tags": options.get("tags") or draft.get("tags", []),
            "video_id": uploaded_video_id,
            "cover": cover_result,
            "tid": options.get("tid"),
            "copyright": options.get("copyright", 1),
            "source": options.get("source", ""),
            "no_reprint": int(bool(options.get("no_reprint", False))),
            "dynamic": options.get("dynamic", ""),
            "mode": mode,
        }
        submit_result = await client.submit_video(cookies, payload)
        data = submit_result.get("data", submit_result)
        external_id = (
            data.get("aid")
            or data.get("bvid")
            or data.get("archive_id")
            or data.get("external_id")
            or ""
        )
        external_url = data.get("url") or (f"https://www.bilibili.com/video/{data.get('bvid')}" if data.get("bvid") else None)

        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "mode": mode,
            "status": "succeeded",
            "external_id": str(external_id),
            "external_url": external_url,
            "external_status": data.get("status", "submitted"),
            "message": "Bilibili video submitted.",
            "api_payload": payload,
            "raw_response": submit_result,
            "upload_response": upload_result,
            "cover_response": cover_result,
        }

    @staticmethod
    def _find_asset(
        assets: list[LocalAsset],
        asset_id: str | None,
        asset_type: str,
    ) -> LocalAsset | None:
        for asset in assets:
            if asset.asset_id == asset_id:
                return asset
        for asset in assets:
            if asset.asset_type == asset_type:
                return asset
        return None
