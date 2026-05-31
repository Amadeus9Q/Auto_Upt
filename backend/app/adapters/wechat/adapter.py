from pathlib import Path
from typing import Any

from backend.app.adapters.base import PlatformAdapter, load_profile
from backend.app.adapters.clients import LocalAsset, PlatformClientError, WechatOfficialAccountClient
from backend.app.adapters.wechat.renderer import render_draft, render_wechat_html


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
        assets: list[LocalAsset] = account.get("assets", [])
        client = WechatOfficialAccountClient()

        # ---- 获取 access_token ----
        token = await client.get_access_token(
            credentials.get("app_id", ""),
            credentials.get("app_secret", ""),
        )
        access_token = token["access_token"]

        # ---- 上传封面图（永久素材）----
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

        # ---- 准备正文 HTML ----
        content_html = draft.get("wechat_html") or self._build_fallback_html(draft)

        # ---- 上传正文内图片并替换 URL ----
        content_html = await self._upload_and_replace_content_images(
            client, access_token, content_html, assets
        )

        # ---- 构建文章 ----
        article = {
            "title": options.get("title") or draft.get("title", ""),
            "author": options.get("author", ""),
            "digest": options.get("digest") or draft.get("summary", ""),
            "content": content_html,
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
                "api_payload": {"articles": [article]},
                "raw_response": draft_result,
            }

        # ---- 发布 ----
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
            "api_payload": {"articles": [article]},
            "raw_response": submit_result,
            "draft_media_id": media_id,
        }

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    @staticmethod
    def _find_cover_asset(
        assets: list[LocalAsset],
        options: dict[str, Any],
    ) -> LocalAsset | None:
        """查找封面图素材。"""
        cover_asset_id = options.get("cover_asset_id")
        for asset in assets:
            if asset.asset_id == cover_asset_id:
                return asset
        for asset in assets:
            if asset.purpose in {"cover", "wechat_cover"} or asset.asset_type == "image":
                return asset
        return None

    @staticmethod
    def _build_fallback_html(draft: dict[str, Any]) -> str:
        """兜底：当 draft 中没有 wechat_html 时，从 text body 构建简单 HTML。

        会自动剥离正文中的 【图片/视频/音频：xxx】 中文媒体标记。
        """
        import re
        body = draft.get("body", "")
        if not body:
            return "<section><p>暂无正文。</p></section>"

        # 移除中文媒体标记
        cn_marker = re.compile(r"【(?:图片|视频|音频)[：:]\s*[^】]+】")
        body = cn_marker.sub("", body)
        body = re.sub(r"\n{3,}", "\n\n", body).strip()

        paragraphs = body.split("\n")
        html_parts = ["<section>"]
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            html_parts.append(
                f'<p style="color:#333;font-size:15px;line-height:2;margin:0 0 12px;">'
                f'{_escape_html(para)}</p>'
            )
        html_parts.append("</section>")
        return "\n".join(html_parts)

    async def _upload_and_replace_content_images(
        self,
        client: WechatOfficialAccountClient,
        access_token: str,
        html_content: str,
        assets: list[LocalAsset],
    ) -> str:
        """将 HTML 中引用的本地图片上传到微信并替换为 CDN URL。

        匹配 <img data-src=\"...\"> 或 <img src=\"...\">，如果 src/data-src
        指向本地文件路径，则上传到微信获取公网 URL 后替换。
        """
        import re

        # 按文件名建立 asset 索引
        asset_by_filename: dict[str, LocalAsset] = {}
        for a in assets:
            name = a.original_filename.lower()
            asset_by_filename[name] = a

        async def replace_img(m: re.Match) -> str:
            tag = m.group(0)
            src = m.group("src") or ""
            if not src:
                return tag

            # 尝试按文件名匹配本地 asset
            src_path = Path(src)
            filename = src_path.name.lower()
            matched = asset_by_filename.get(filename)

            if matched and matched.file_path:
                try:
                    upload_result = await client.upload_content_image(
                        access_token,
                        matched.file_path,
                        filename=matched.original_filename,
                        content_type=matched.content_type or "image/png",
                    )
                    wechat_url = upload_result.get("url", "")
                    if wechat_url:
                        return re.sub(
                            r'(data-src|src)="[^"]*"',
                            f'data-src="{_escape_html(wechat_url)}"',
                            tag,
                        )
                except PlatformClientError:
                    pass  # 上传失败则保留原始标签

            return tag

        # 匹配 <img ... src="..." ...> 或 <img ... data-src="..." ...>
        pattern = re.compile(r'<img\s+[^>]*(?:data-src|src)="(?P<src>[^"]*)"[^>]*>')

        # 逐个匹配（同步上传）
        result = html_content
        for m in pattern.finditer(html_content):
            replacement = await replace_img(m)
            result = result.replace(m.group(0), replacement, 1)

        return result


def _escape_html(text: str) -> str:
    """HTML 转义，防止 XSS。"""
    from html import escape
    return escape(text)
