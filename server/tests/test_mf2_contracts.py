# -*- coding: utf-8 -*-
"""MF2 契约测试：步骤级续跑端点 + appearance 外观设置组 + 模型切换代理。

不依赖真实 PostgreSQL（app_settings 走 DB 不可用降级路径）与 AI 引擎
（引擎不可达统一 4004 信封）；续跑测试的任务记录直接注入内存
（不入创建队列），失败步骤用未知任务类型（MODULE_MAP 查不到→秒失败，
不会拉起真实子进程、不出网）。
"""
from __future__ import annotations

import time
import uuid as uuid_lib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from astroforge.core.task_scheduler import TaskRecord


@pytest.fixture()
def client(tmp_settings: Path) -> TestClient:
    from astroforge.api.app import create_app
    from astroforge.core.config_loader import load_settings

    app = create_app(load_settings(tmp_settings))
    with TestClient(app) as test_client:
        ctx = app.state.context
        test_client.headers.update({"X-AstroForge-Token": ctx.token})
        yield test_client


def _inject_failed_task(scheduler) -> TaskRecord:
    """构造一个已失败的双步流水线任务（step0 成功 / step1 失败），不入队列。"""
    record = TaskRecord(
        task_uuid=str(uuid_lib.uuid4()), task_type="spider_site", mode="pipeline",
        title="续跑测试", config={"pipeline": "paper_process"},
    )
    record.status = "failed"
    record.error_code = 3003
    record.steps = [
        {"step_index": 0, "step_name": "已完成步", "task_type": "anydoc",
         "status": "success"},
        # 未知任务类型：续跑后 worker 直接按 1001 失败，零子进程零出网
        {"step_index": 1, "step_name": "失败步", "task_type": "no_such_module",
         "status": "failed"},
    ]
    scheduler._tasks[record.task_uuid] = record
    return record


# ============================================================
# appearance 外观设置组（V1-B.6 / MF2 设置页外观组）
# ============================================================

def test_appearance_keys_in_writable_whitelist() -> None:
    from astroforge.api.routes_system import WRITABLE_KEYS

    assert "appearance.theme" in WRITABLE_KEYS
    assert WRITABLE_KEYS["appearance.theme"] == (str,)
    assert WRITABLE_KEYS["appearance.starfield"] == (bool,)
    assert WRITABLE_KEYS["appearance.mascot"] == (bool,)


def test_config_summary_exposes_appearance(client: TestClient) -> None:
    resp = client.get("/api/v1/system/config-summary")
    assert resp.json()["code"] == 0
    appearance = resp.json()["data"]["appearance"]
    assert appearance["theme"] == "deep-space"  # §2.2 内置夜默认
    assert appearance["starfield"] is True
    assert "mascot" in appearance


def test_set_appearance_theme_roundtrip(client: TestClient, monkeypatch) -> None:
    """覆盖合并逻辑：monkeypatch 仓储层（测试环境无真实 PG，不入库断言走 2004）。"""
    import astroforge.db.repositories.app_settings as settings_repo

    async def fake_list_all(session, keys):
        return {"appearance.theme": {"value": "dawn"}} if "appearance.theme" in keys else {}

    monkeypatch.setattr(settings_repo, "list_all", fake_list_all)
    summary = client.get("/api/v1/system/config-summary").json()["data"]
    assert summary["appearance"]["theme"] == "dawn"  # 覆盖值回读


def test_set_appearance_persist_requires_db(client: TestClient) -> None:
    """无可用 PG 时写入被拒绝（DB_UNAVAILABLE 信封），不静默丢失。"""
    resp = client.put("/api/v1/app-settings/appearance.theme", json={"value": "dawn"})
    assert resp.json()["code"] == 2004


def test_set_appearance_rejects_wrong_type(client: TestClient) -> None:
    resp = client.put("/api/v1/app-settings/appearance.theme", json={"value": 123})
    assert resp.json()["code"] == 1001  # 类型不符（str 白名单）


def test_set_appearance_rejects_out_of_whitelist(client: TestClient) -> None:
    resp = client.put("/api/v1/app-settings/appearance.font", json={"value": "x"})
    assert resp.json()["code"] == 1001


# ============================================================
# 模型切换代理（MF2 星伴模型胶囊）
# ============================================================

def test_model_switch_rejects_unknown_key(client: TestClient) -> None:
    resp = client.post("/api/v1/ai/model/switch", json={"model_key": "gpt-9"})
    assert resp.json()["code"] == 1001


def test_model_switch_engine_unreachable(client: TestClient) -> None:
    resp = client.post("/api/v1/ai/model/switch", json={"model_key": "qwen2b"})
    assert resp.json()["code"] == 4004  # 引擎不可达统一信封


# ============================================================
# 步骤级续跑（UX P0-2 / 方案 V1.1-6 唯一服务端补的 API）
# ============================================================

def test_retry_step_semantics(client: TestClient) -> None:
    scheduler = client.app.state.context.scheduler  # type: ignore[attr-defined]
    record = _inject_failed_task(scheduler)

    # 非失败步骤 / 越界 / 非失败任务 → 拒绝（经端点校验）
    for url in (
        f"/api/v1/tasks/{record.task_uuid}/steps/0/retry",
        f"/api/v1/tasks/{record.task_uuid}/steps/9/retry",
    ):
        assert client.post(url).json()["code"] == 1001

    # 失败步骤续跑：200 且原地更新同一任务
    resp = client.post(f"/api/v1/tasks/{record.task_uuid}/steps/1/retry")
    body = resp.json()
    assert body["code"] == 0
    data = body["data"]
    assert data["task_uuid"] == record.task_uuid      # 不裂成新任务
    assert data["status"] == "pending"
    assert data["steps"][0]["status"] == "success"    # 已完成步骤产物保留
    assert data["steps"][1]["status"] == "pending"    # 失败步骤重置待跑
    assert data["error_code"] is None


def test_retry_step_rerun_fails_fast_without_subprocess(client: TestClient) -> None:
    """续跑后 worker 复跑：未知任务类型秒失败（1001），step0 不重跑。"""
    scheduler = client.app.state.context.scheduler  # type: ignore[attr-defined]
    record = _inject_failed_task(scheduler)
    assert client.post(
        f"/api/v1/tasks/{record.task_uuid}/steps/1/retry").json()["code"] == 0

    # 等 worker 串行复跑完成（内存队列；未知类型即时失败）
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        detail = client.get(f"/api/v1/tasks/{record.task_uuid}").json()["data"]
        if detail["status"] == "failed":
            break
        time.sleep(0.05)
    assert detail["status"] == "failed"
    assert detail["error_code"] == 1001
    assert [s["status"] for s in detail["steps"]] == ["success", "failed"]
