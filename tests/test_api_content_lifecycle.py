import io

import pytest

from backend.app.agents.document_extractor import DocumentExtractorAgent, _rule_based_extract


@pytest.mark.asyncio
async def test_dep_010_health_returns_json(api_client) -> None:
    response = await api_client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_cnt_006_lists_supported_platforms(api_client) -> None:
    response = await api_client.get("/api/v1/content/platforms")

    assert response.status_code == 200
    assert set(response.json()["platforms"]) == {"wechat", "zhihu", "xiaohongshu", "bilibili"}


@pytest.mark.asyncio
async def test_cnt_001_cnt_002_normalizes_title_and_tags(api_client) -> None:
    response = await api_client.post(
        "/api/v1/content/normalize",
        json={
            "body": "自动推断标题\n\n正文内容",
            "tags": ["#AI", "AI", "内容运营"],
        },
    )

    assert response.status_code == 200
    content_ir = response.json()["content_ir"]
    assert content_ir["title"] == "自动推断标题"
    assert content_ir["tags"] == ["AI", "内容运营"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("payload", "expected_status"),
    [
        ({"body": ""}, 422),
        ({"title": "标" * 161, "body": "正文"}, 422),
        ({"body": "正文", "content_type": "unknown"}, 422),
    ],
    ids=["CNT-003-empty-body", "CNT-004-long-title", "SEC-003-invalid-enum"],
)
async def test_content_input_validation(api_client, payload: dict, expected_status: int) -> None:
    response = await api_client.post("/api/v1/content/normalize", json=payload)

    assert response.status_code == expected_status


@pytest.mark.asyncio
async def test_cnt_005_preserves_content_block_order(api_client) -> None:
    blocks = [
        {"type": "text", "text": "图片之前"},
        {"type": "asset", "asset_id": "image-1", "asset_kind": "image", "role": "inline"},
        {"type": "text", "text": "图片之后"},
    ]
    response = await api_client.post(
        "/api/v1/content/normalize",
        json={
            "body": "图片之前\n图片之后",
            "assets": [{"id": "image-1", "name": "正文图片.png", "type": "image"}],
            "content_blocks": blocks,
        },
    )

    assert response.status_code == 200
    normalized_blocks = response.json()["content_ir"]["body_blocks"]
    assert [block["type"] for block in normalized_blocks] == ["text", "asset", "text"]
    assert normalized_blocks[1]["asset_id"] == "image-1"
    assert normalized_blocks[1]["asset"]["name"] == "正文图片.png"


@pytest.mark.asyncio
async def test_prv_001_generates_all_platform_drafts(api_client, article_payload) -> None:
    response = await api_client.post("/api/v1/content/adapt", json=article_payload)

    assert response.status_code == 200
    result = response.json()
    assert set(result["drafts"]) == {"wechat", "zhihu", "xiaohongshu", "bilibili"}
    assert set(result["validation_report"]) == set(result["drafts"])


@pytest.mark.asyncio
async def test_prv_002_generates_only_selected_platforms(api_client, article_payload) -> None:
    payload = {**article_payload, "platforms": ["wechat", "zhihu"]}
    response = await api_client.post("/api/v1/content/adapt", json=payload)

    assert response.status_code == 200
    assert set(response.json()["drafts"]) == {"wechat", "zhihu"}


@pytest.mark.asyncio
async def test_prv_003_rejects_unknown_platform(api_client, article_payload) -> None:
    response = await api_client.post(
        "/api/v1/content/adapt",
        json={**article_payload, "platforms": ["wechat", "unknown"]},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_prv_012_revalidates_edited_platform_draft(api_client) -> None:
    response = await api_client.patch(
        "/api/v1/previews/local-preview/drafts/wechat",
        json={"title": "标题", "body": "修改后的正文", "summary": "摘要", "tags": ["AI"]},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["preview_id"] == "local-preview"
    assert result["drafts"]["wechat"]["body"] == "修改后的正文"
    assert "wechat" in result["validation_report"]


@pytest.mark.asyncio
async def test_analysis_content_and_full_lifecycle(api_client, article_payload) -> None:
    analysis_response = await api_client.post("/api/v1/analysis/content", json=article_payload)
    full_response = await api_client.post(
        "/api/v1/analysis/full",
        json={"request": article_payload, "platforms": None},
    )

    assert analysis_response.status_code == 200
    assert analysis_response.json()["flat_chapters"]
    assert full_response.status_code == 200
    assert set(full_response.json()["platform_copies"]) == {"wechat", "zhihu", "xiaohongshu", "bilibili"}


@pytest.mark.asyncio
async def test_agt_002_rule_agent_preview_never_publishes(api_client, article_payload) -> None:
    response = await api_client.post(
        "/api/v1/agent-runs/preview",
        json={**article_payload, "platforms": ["wechat", "bilibili"], "include_simulation": True},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["mode"] == "simulate"
    assert set(result["drafts"]) == {"wechat", "bilibili"}
    assert set(result["simulation_results"]) == {"wechat", "bilibili"}


@pytest.mark.asyncio
async def test_imp_001_imports_markdown_with_rule_extractor(api_client, monkeypatch) -> None:
    monkeypatch.setattr(DocumentExtractorAgent, "extract", lambda self, text: _rule_based_extract(text))
    markdown = "# 导入标题\n\n标签：AI,内容运营\n\n## 第一节\n\n正文内容\n\n![示例图](images/demo.png)"

    response = await api_client.post(
        "/api/v1/content/import",
        files={"file": ("article.md", io.BytesIO(markdown.encode("utf-8")), "text/markdown")},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["title"] == "导入标题"
    assert result["body"]
    assert result["raw_text"]
    assert any(item["name"] == "demo.png" for item in result["media"])


@pytest.mark.asyncio
async def test_imp_005_rejects_unsupported_document(api_client) -> None:
    response = await api_client.post(
        "/api/v1/content/import",
        files={"file": ("article.pdf", io.BytesIO(b"not a pdf"), "application/pdf")},
    )

    assert response.status_code == 400
    assert "不支持的文件格式" in response.json()["detail"]
