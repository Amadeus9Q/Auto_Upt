from backend.app.adapters.wechat.renderer import render_wechat_html


def test_body_blocks_render_inline_image_when_chapters_exist() -> None:
    content_ir = {
        "title": "Article",
        "body": "Before\n{{asset:image:image-id}}\nAfter",
        "chapters": [{"title": "Generated chapter", "content": "Chapter text"}],
        "body_blocks": [
            {"type": "text", "text": "Before"},
            {
                "type": "asset",
                "asset_kind": "image",
                "asset": {
                    "id": "image-id",
                    "type": "image",
                    "name": "article-image.png",
                    "preview_url": "blob:http://localhost/image-id",
                },
            },
            {"type": "text", "text": "After"},
        ],
    }

    result = render_wechat_html(content_ir)

    assert 'data-src="blob:http://localhost/image-id"' in result
    assert 'alt="article-image.png"' in result
    assert "Before" in result
    assert "After" in result
