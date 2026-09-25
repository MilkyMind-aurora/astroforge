# -*- coding: utf-8 -*-
"""MF3.5 契约测试：步骤级续跑 API 语义补全 + 错误码分段（UX P0-2）。

覆盖点：仅失败/未运行步骤可续跑（success/running 目标拒绝）、终态任务门槛
（running/pending 任务拒绝防双跑）、已完成步骤产物保留、取消残留事件清理、
错误码分段（任务不存在=4001 资源 / 状态不合法=1001 参数）。
不依赖真实 PostgreSQL（内存态）；失败步骤用未知任务类型（MODULE_MAP 查不到
→ worker 秒失败，不拉起真实子进程、不出网）。
"""
from __future__ import annotations

import time
import uuid as uuid_lib
from pathlib import Path
from typing import Any

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


def _inject_task(
    scheduler,
    status: str,
    step_statuses: list[str],
    *,
    cancel_event_set: bool = False,
) -> TaskRecord:
    """注入指定状态的内存任务（不入创建队列）；第 2 步固定用未知任务类型，
    续跑后 worker 即时失败（1001），零子进程零出网。"""
    record = TaskRecord(
        task_uuid=str(uuid_lib.uuid4()), task_type="spider_site", mode="pipeline",
        title="MF3.5 续跑测试", config={"pipeline": "paper_process"},
    )
    record.status = status
    if cancel_event_set:
        record.cancel_event.set()  # 模拟「运行中取消」后的残留标志
    record.steps = [
        {"step_index": i, "step_name": f"步骤{i}", "task_type": task_type,
         "status": step_status}
        for i, (task_type, step_status) in enumerate(
            zip(["anydoc", "no_such_module", "md2docx"], step_statuses))
    ]
    scheduler._tasks[record.task_uuid] = record
    return record


def _retry(client: TestClient, task_uuid: str, step_index: int) -> dict[str, Any]:
    return client.post(
        f"/api/v1/tasks/{task_uuid}/steps/{step_index}/retry").json()


def _wait_terminal(client: TestClient, task_uuid: str, timeout: float = 5.0) -> dict:
    """等 worker 串行复跑至终态（内存队列；未知任务类型即时失败）。"""
    deadline = time.monotonic() + timeout
    detail: dict = {}
    while time.monotonic() < deadline:
        detail = client.get(f"/api/v1/tasks/{task_uuid}").json()["data"]
        if detail["status"] in {"success", "failed", "canceled"}:
            return detail
        time.sleep(0.05)
    raise AssertionError(f"任务未在 {timeout}s 内到达终态: {detail}")


# ============================================================
# 错误码分段（4001 资源 / 1001 参数）
# ============================================================

def test_retry_step_missing_task_is_4001(client: TestClient) -> None:
    """任务不存在=资源类 4001（与任务详情路由同段），不再混入 1xxx 参数段。"""
    missing = str(uuid_lib.uuid4())
    body = _retry(client, missing, 0)
    assert body["code"] == 4001
    assert "任务不存在" in body["message"]


def test_retry_step_rejects_non_resumable_step_targets(client: TestClient) -> None:
    """仅失败/未运行步骤可续跑：success 目标与越界一律 1001 参数段。"""
    scheduler = client.app.state.context.scheduler  # type: ignore[attr-defined]
    record = _inject_task(scheduler, "failed", ["success", "failed", "pending"])
    for step_index in (0, 3):  # success 步（0）/ 越界步（3）
        assert _retry(client, record.task_uuid, step_index)["code"] == 1001
    # 人造 running 步（正常状态机不会出现，防御分支仍须拒绝）
    record.steps[1]["status"] = "running"
    assert _retry(client, record.task_uuid, 1)["code"] == 1001


def test_retry_step_rejects_running_task(client: TestClient) -> None:
    """运行中任务的 pending 步不可续跑（防重复入队双跑）→ 1001。"""
    scheduler = client.app.state.context.scheduler  # type: ignore[attr-defined]
    record = _inject_task(scheduler, "running", ["success", "running", "pending"])
    assert _retry(client, record.task_uuid, 2)["code"] == 1001
    assert record.status == "running"  # 原任务状态不被续跑请求破坏


def test_retry_step_rejects_queued_pending_task(client: TestClient) -> None:
    """排队中的任务本就会执行，续跑请求视为参数不合法 → 1001。"""
    scheduler = client.app.state.context.scheduler  # type: ignore[attr-defined]
    record = _inject_task(scheduler, "pending", ["pending", "pending", "pending"])
    assert _retry(client, record.task_uuid, 0)["code"] == 1001


def test_retry_step_rejects_success_task(client: TestClient) -> None:
    """成功任务无可续跑步骤（全 success）→ 1001。"""
    scheduler = client.app.state.context.scheduler  # type: ignore[attr-defined]
    record = _inject_task(scheduler, "success", ["success", "success", "success"])
    assert _retry(client, record.task_uuid, 0)["code"] == 1001


# ============================================================
# 续跑语义：原地更新 / 产物保留 / 终态任务门槛放行
# ============================================================

def test_retry_step_failed_task_pending_step_resumes_in_place(
    client: TestClient,
) -> None:
    """失败任务的未运行步骤可续跑：同 uuid 原地更新，已完成步骤保留。"""
    scheduler = client.app.state.context.scheduler  # type: ignore[attr-defined]
    record = _inject_task(scheduler, "failed", ["success", "failed", "pending"])
    record.error_code = 3003
    record.error_message = "步骤失败"
    record.finished_at = "2026-09-25T00:00:00+00:00"

    body = _retry(client, record.task_uuid, 2)  # 续跑未运行步（200）
    assert body["code"] == 0
    data = body["data"]
    assert data["task_uuid"] == record.task_uuid  # 不裂成新任务
    assert data["status"] == "pending"
    assert data["error_code"] is None             # 旧失败语义清空
    assert data["finished_at"] is None
    assert [s["status"] for s in data["steps"]] == ["success", "failed", "pending"]


def test_retry_step_worker_rerun_preserves_completed_steps(
    client: TestClient,
) -> None:
    """复跑回归：已完成步骤不重跑（产物保留），失败步重跑后未运行步不动。"""
    scheduler = client.app.state.context.scheduler  # type: ignore[attr-defined]
    record = _inject_task(scheduler, "failed", ["success", "failed", "pending"])
    assert _retry(client, record.task_uuid, 1)["code"] == 0

    detail = _wait_terminal(client, record.task_uuid)
    assert detail["status"] == "failed"
    assert detail["error_code"] == 1001           # 未知任务类型秒失败（无子进程）
    assert [s["status"] for s in detail["steps"]] == ["success", "failed", "pending"]


def test_retry_step_canceled_task_clears_cancel_event(client: TestClient) -> None:
    """取消任务续跑：残留 cancel_event 必须清理，否则复跑在循环顶端被
    立刻再次取消（终态会是 canceled 而非真实执行结果）。"""
    scheduler = client.app.state.context.scheduler  # type: ignore[attr-defined]
    record = _inject_task(
        scheduler, "canceled", ["success", "pending", "pending"],
        cancel_event_set=True,
    )
    body = _retry(client, record.task_uuid, 1)  # 未运行步骤可续跑（200）
    assert body["code"] == 0
    assert body["data"]["status"] == "pending"

    detail = _wait_terminal(client, record.task_uuid)
    assert detail["status"] == "failed"           # 真实复跑（而非被取消吞掉）
    assert detail["error_code"] == 1001
