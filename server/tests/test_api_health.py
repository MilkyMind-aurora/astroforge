"""API 冒烟测试：健康检查（开放）+ 认证门禁 + 任务列表（TestClient，无需 PostgreSQL）。"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_settings: Path) -> TestClient:
    from astroforge.api.app import create_app
    from astroforge.core.config_loader import load_settings

    app = create_app(load_settings(tmp_settings))
    with TestClient(app) as test_client:
        # 读取 lifespan 生成的 token 供认证请求使用
        ctx = app.state.context
        test_client.headers.update({"X-AstroForge-Token": ctx.token})
        yield test_client


def test_health_open_without_token(client: TestClient):
    client.headers.pop("X-AstroForge-Token", None)
    resp = client.get("/api/v1/system/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["code"] == 0
    assert body["data"]["service"] == "sidereal-core"
    assert body["data"]["project"] == "AstroForge"


def test_tasks_requires_token(client: TestClient):
    client.headers.pop("X-AstroForge-Token", None)
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 401
    assert resp.json()["code"] == 2001


def test_tasks_list_with_token(client: TestClient):
    resp = client.get("/api/v1/tasks")
    assert resp.status_code == 200
    assert resp.json()["code"] == 0
    assert resp.json()["data"]["items"] == []


def test_create_unknown_task_type(client: TestClient):
    resp = client.post("/api/v1/tasks", json={"task_type": "nuke_everything"})
    assert resp.status_code == 200  # 业务错误走统一信封
    assert resp.json()["code"] == 1001


def test_pipelines_seeded(client: TestClient):
    resp = client.get("/api/v1/pipelines")
    assert resp.json()["code"] == 0
    names = [p["name"] for p in resp.json()["data"]["items"]]
    assert {"paper_process", "doc_crawl", "office_batch", "math_data"}.issubset(set(names))


def test_monitor_history_validation(client: TestClient):
    resp = client.get("/api/v1/monitor/history", params={"range": "9h"})
    assert resp.json()["code"] == 1001


def test_env_check_summary(client: TestClient):
    resp = client.get("/api/v1/system/env-check")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] >= 8
    assert all({"name", "ok", "detail"} <= set(item) for item in data["items"])
