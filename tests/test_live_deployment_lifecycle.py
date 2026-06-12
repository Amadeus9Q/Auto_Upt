import os
import time
from uuid import uuid4

import httpx
import pytest


pytestmark = pytest.mark.live

BASE_URL = os.getenv("AUTO_UPT_TEST_BASE_URL", "http://localhost").rstrip("/")
RUN_LIVE = os.getenv("AUTO_UPT_RUN_LIVE_TESTS") == "1"


def _client() -> httpx.Client:
    return httpx.Client(base_url=BASE_URL, timeout=30, trust_env=False)


def _wait_until_ready(client: httpx.Client, timeout_seconds: float = 30) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if client.get("/api/v1/content/platforms").status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    pytest.fail(f"Deployment did not become ready within {timeout_seconds} seconds.")


@pytest.mark.skipif(not RUN_LIVE, reason="Set AUTO_UPT_RUN_LIVE_TESTS=1 to test a running deployment.")
def test_dep_009_dep_010_live_frontend_and_health() -> None:
    with _client() as client:
        _wait_until_ready(client)
        frontend = client.get("/")
        health = client.get("/api/v1/content/platforms")

    assert frontend.status_code == 200
    assert health.status_code == 200


@pytest.mark.skipif(not RUN_LIVE, reason="Set AUTO_UPT_RUN_LIVE_TESTS=1 to test a running deployment.")
def test_ast_001_ast_004_ast_005_ast_006_live_asset_crud() -> None:
    filename = f"automation-{uuid4()}.txt"
    with _client() as client:
        _wait_until_ready(client)
        created = client.post(
            "/api/v1/assets",
            files={"file": (filename, b"automation asset", "text/plain")},
            data={"asset_type": "file", "purpose": "content"},
        )
        assert created.status_code == 200
        asset_id = created.json()["asset_id"]

        listed = client.get("/api/v1/assets")
        detail = client.get(f"/api/v1/assets/{asset_id}")
        downloaded = client.get(f"/api/v1/assets/{asset_id}/download")
        deleted = client.delete(f"/api/v1/assets/{asset_id}")
        missing = client.get(f"/api/v1/assets/{asset_id}")

    assert any(asset["asset_id"] == asset_id for asset in listed.json()["assets"])
    assert detail.status_code == 200
    assert downloaded.content == b"automation asset"
    assert deleted.status_code == 200
    assert missing.status_code == 404


@pytest.mark.skipif(not RUN_LIVE, reason="Set AUTO_UPT_RUN_LIVE_TESTS=1 to test a running deployment.")
def test_pub_001_pub_003_tsk_001_tsk_003_live_simulation_lifecycle() -> None:
    preview_id = str(uuid4())
    draft = {"title": "自动化模拟发布", "body": "模拟发布正文", "summary": "摘要", "tags": ["自动化"]}
    payload = {
        "preview_id": preview_id,
        "mode": "simulate",
        "platforms": ["wechat", "zhihu"],
        "inline_drafts": {"wechat": draft, "zhihu": draft},
        "inline_content_ir": {"title": draft["title"], "body": draft["body"], "tags": draft["tags"]},
    }

    with _client() as client:
        _wait_until_ready(client)
        created = client.post("/api/v1/publish-tasks", json=payload)
        assert created.status_code == 200
        task_id = created.json()["task_id"]
        detail = client.get(f"/api/v1/publish-tasks/{task_id}")
        listed = client.get("/api/v1/publish-tasks", params={"mode": "simulate", "limit": 100})

    assert created.json()["status"] == "succeeded"
    assert set(created.json()["results"]) == {"wechat", "zhihu"}
    assert detail.status_code == 200
    assert any(task["task_id"] == task_id for task in listed.json()["tasks"])


@pytest.mark.external_publish
@pytest.mark.skip(reason="Real platform publishing is intentionally never run by the default automation suite.")
def test_real_platform_publish_is_guarded() -> None:
    """Placeholder guard for PUB-006/PUB-007/PUB-010 and publication mutation cases."""
