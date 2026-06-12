from collections.abc import AsyncIterator

import httpx
import pytest

from backend.app.main import app


@pytest.fixture
async def api_client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
def article_payload() -> dict:
    return {
        "title": "AI 内容运营助手",
        "body": "# AI 内容运营助手\n\n## 工作流\n\n统一编辑并生成多平台预览。",
        "content_type": "article",
        "tags": ["#AI", "内容运营", "AI"],
    }

