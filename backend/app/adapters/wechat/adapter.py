from pathlib import Path
from typing import Any

from backend.app.adapters.base import PlatformAdapter, load_profile
from backend.app.adapters.clients import LocalAsset, PlatformClientError, WechatOfficialAccountClient
from backend.app.adapters.wechat.renderer import render_draft


class WechatAdapter(PlatformAdapter):
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
                "WeChat account credentials are required for real publish.",
                platform_code="ACCOUNT_REQUIRED",
                next_action="请先连接公众号账号，并在发布请求中传入 account_ids.wechat。",
            )

        credentials = account.get("credentials", {})
        options = account.get("options", {})
        assets = account.get("assets", [])
        client = WechatOfficialAccountClient()
        token = await client.get_access_token(
            credentials.get("app_id", ""),
            credentials.get("app_secret", ""),
        )
        access_token = token["access_token"]

        cover_asset = self._find_cover_asset(assets, options)
        if cover_asset is None:
            raise PlatformClientError(
                "WeChat publish requires a cover image asset.",
                platform_code="COVER_REQUIRED",
                next_action="请先上传封面图，并在 platform_options.wechat.cover_asset_id 或 asset_ids.wechat 中传入。",
            )

        cover_upload = await client.upload_permanent_asset(
            access_token,
            cover_asset,
            material_type="image",
        )

        article = {
            "title": options.get("title") or draft.get("title", ""),
            "author": options.get("author", ""),
            "digest": options.get("digest") or draft.get("summary", ""),
            "content": draft.get("body", ""),
            "content_source_url": options.get("content_source_url", ""),
            "thumb_media_id": cover_upload["media_id"],
            "need_open_comment": int(bool(options.get("need_open_comment", False))),
            "only_fans_can_comment": int(bool(options.get("only_fans_can_comment", False))),
        }
        draft_result = await client.add_draft(access_token, article)
        media_id = draft_result["media_id"]

        if mode == "draft":
            return {
                "platform": self.platform,
                "display_name": self.display_name,
                "mode": mode,
                "status": "succeeded",
                "external_id": media_id,
                "external_status": "draft_created",
                "message": "WeChat draft created.",
                "raw_response": draft_result,
            }

        submit_result = await client.submit_publish(access_token, media_id)
        publish_id = str(submit_result.get("publish_id", ""))
        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "mode": mode,
            "status": "succeeded",
            "external_id": publish_id,
            "external_status": "submitted",
            "message": "WeChat publish submitted.",
            "raw_response": submit_result,
            "draft_media_id": media_id,
        }

    @staticmethod
    def _find_cover_asset(
        assets: list[LocalAsset],
        options: dict[str, Any],
    ) -> LocalAsset | None:
        cover_asset_id = options.get("cover_asset_id")
        for asset in assets:
            if asset.asset_id == cover_asset_id:
                return asset
        for asset in assets:
            if asset.purpose in {"cover", "wechat_cover"} or asset.asset_type == "image":
                return asset
        return None
