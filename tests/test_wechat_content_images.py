import asyncio

from backend.app.adapters.clients import LocalAsset
from backend.app.adapters.wechat.adapter import WechatAdapter


class FakeWechatClient:
    async def upload_content_image(
        self,
        access_token: str,
        image_path: str,
        filename: str,
        content_type: str,
    ) -> dict[str, str]:
        assert access_token == "token"
        assert filename == "article-image.png"
        return {"url": "https://mmbiz.qpic.cn/article-image.png"}


def test_blob_content_image_is_matched_by_alt_filename() -> None:
    html = '<p>Article body</p><img data-src="blob:http://localhost/random-id" alt="article-image.png" />'
    asset = LocalAsset(
        asset_id="asset-id",
        asset_type="image",
        purpose="wechat_body_image",
        original_filename="article-image.png",
        content_type="image/png",
        file_path="storage/assets/article-image.png",
        file_size=10,
        sha256="hash",
    )

    result = asyncio.run(
        WechatAdapter()._upload_and_replace_content_images(
            FakeWechatClient(),
            "token",
            html,
            [asset],
        )
    )

    assert 'src="https://mmbiz.qpic.cn/article-image.png"' in result
    assert "blob:http://localhost/random-id" not in result
