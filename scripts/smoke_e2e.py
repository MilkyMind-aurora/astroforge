# -*- coding: utf-8 -*-
"""Phase 7 端到端冒烟矩阵：对运行中的 Sidereal Core 依次验证核心链路。

前置：服务核心已启动（scripts/start_service.bat|.sh）；ASTROFORGE_PG_PASSWORD 已设置。
用法：python scripts/smoke_e2e.py [--port 8420] [--skip-ai]
输出：PASS/FAIL/SKIP 矩阵；任一 FAIL 退出码 1。
安全约定：仅允许对本机回环地址的 Sidereal Core 发起请求（显式校验，非限定）。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}

RESULTS: list[tuple[str, str, str]] = []  # (用例, 结果, 备注)


def _check_base(host: str) -> None:
    """运维脚本只允许打本机服务；其他目标直接拒绝启动。"""
    if host.lower() not in ALLOWED_HOSTS:
        raise SystemExit(f"拒绝：本脚本仅允许回环目标，收到 {host}")


def _record(name: str, ok: bool | None, note: str = "") -> None:
    mark = "SKIP" if ok is None else ("PASS" if ok else "FAIL")
    RESULTS.append((name, mark, note))
    print(f"[{mark}] {name}  {note}")


def main() -> int:
    parser = argparse.ArgumentParser(description="AstroForge 端到端冒烟矩阵")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8420)
    parser.add_argument("--skip-ai", action="store_true", help="跳过 AI 用例（引擎未启动时）")
    parser.add_argument("--wait-seconds", type=int, default=90, help="任务完成轮询上限")
    args = parser.parse_args()
    _check_base(args.host)
    token = (REPO_ROOT / "data" / "service_token").read_text(encoding="utf-8").strip()
    headers = {"X-AstroForge-Token": token}
    client = httpx.Client(
        base_url=f"http://{args.host}:{args.port}", headers=headers, timeout=30.0
    )

    # 1. 健康检查
    try:
        resp = client.get("/api/v1/system/health")
        data = resp.json().get("data", {})
        _record("健康检查", resp.status_code == 200 and data.get("db") is True,
                f"db={data.get('db')} ai={data.get('ai_engine')}")
    except Exception as exc:
        _record("健康检查", False, str(exc))
        _summary()
        return 1

    # 2. 环境自检
    try:
        body = client.get("/api/v1/system/env-check").json()
        items = body["data"]["items"]
        failed = [i["name"] for i in items if not i["ok"]]
        _record("环境自检", True,
                f"{body['data']['ok_count']}/{body['data']['total']}，未过: {failed or '无'}")
    except Exception as exc:
        _record("环境自检", False, str(exc))

    # 3. 认证门禁（无 token 必须被拒）
    try:
        resp = httpx.get(f"{client.base_url}/api/v1/tasks", timeout=10.0)
        _record("认证门禁", resp.status_code == 401, f"HTTP {resp.status_code}")
    except Exception as exc:
        _record("认证门禁", False, str(exc))

    # 4. 端到端任务（真实爬取 example.com）
    try:
        body = client.post("/api/v1/tasks", json={
            "task_type": "spider_single",
            "config": {"url": "https://example.com",
                       "output_dir": str(REPO_ROOT / "data" / "cache" / "e2e_smoke")},
            "title": "冒烟-单页爬取",
        }).json()
        task_uuid = body["data"]["task_uuid"]
        deadline = time.time() + args.wait_seconds
        final = None
        while time.time() < deadline:
            detail = client.get(f"/api/v1/tasks/{task_uuid}").json()["data"]
            final = detail["status"]
            if final in {"success", "failed", "canceled"}:
                break
            time.sleep(2)
        _record("端到端任务(spider_single)", final == "success", f"status={final}")
    except Exception as exc:
        _record("端到端任务(spider_single)", False, str(exc))

    # 5. 流水线模板就绪（不实际执行，避免重负载）
    try:
        names = {p["name"] for p in client.get("/api/v1/pipelines").json()["data"]["items"]}
        expected = {"paper_process", "doc_crawl", "office_batch", "math_data"}
        _record("NovaFlow 内置模板", expected <= names, f"缺: {expected - names or '无'}")
    except Exception as exc:
        _record("NovaFlow 内置模板", False, str(exc))

    # 6. 设置回环
    try:
        client.put("/api/v1/app-settings/memory_warning_gb", json={"value": 10.5})
        current = (client.get("/api/v1/app-settings").json()["data"]["items"]
                   .get("memory_warning_gb", {}).get("value"))
        _record("设置回环", current == 10.5, f"value={current}")
    except Exception as exc:
        _record("设置回环", False, str(exc))

    # 7. AI 对话（三层解析 + 兜底派发；引擎未启动则 SKIP）
    if args.skip_ai:
        _record("AI 指令链路", None, "--skip-ai")
    else:
        try:
            engine_up = httpx.get("http://127.0.0.1:8421/v1/health", timeout=3.0).status_code == 200
        except Exception:
            engine_up = False
        if not engine_up:
            _record("AI 指令链路", None, "AI 引擎未启动（modules/ai_engine）")
        else:
            try:
                resp = client.post("/api/v1/ai/chat",
                                   json={"message": "帮我爬取 https://example.com 首页"},
                                   timeout=300.0)
                body = resp.json()
                if body.get("code") != 0:
                    _record("AI 指令链路", False, f"code={body.get('code')} {body.get('message')}")
                else:
                    data = body["data"]
                    ok = data.get("instruction") is not None and data.get("task_uuid")
                    _record("AI 指令链路", bool(ok),
                            f"fallback={data.get('fallback')} task={str(data.get('task_uuid'))[:8]}")
            except Exception as exc:
                _record("AI 指令链路", False, str(exc))

    passed = sum(1 for _, m, _ in RESULTS if m == "PASS")
    failed = sum(1 for _, m, _ in RESULTS if m == "FAIL")
    skipped = sum(1 for _, m, _ in RESULTS if m == "SKIP")
    print(f"\n矩阵结果: {passed} PASS / {failed} FAIL / {skipped} SKIP")
    return 1 if failed else 0


def _summary() -> None:
    passed = sum(1 for _, m, _ in RESULTS if m == "PASS")
    failed = sum(1 for _, m, _ in RESULTS if m == "FAIL")
    skipped = sum(1 for _, m, _ in RESULTS if m == "SKIP")
    print(f"\n矩阵结果: {passed} PASS / {failed} FAIL / {skipped} SKIP")


if __name__ == "__main__":
    sys.exit(main())
