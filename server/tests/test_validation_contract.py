"""校验错误契约测试（终审 L28）：RequestValidationError 一律 HTTP 400 + fail(1001) 统一信封。

修复前失真：docs/openapi.json 记载 422 Validation Error，但 app.py 的
validation_handler 漏传 status_code，实际返回 200+1001——代码与契约双向失真。
修复后：代码 400+1001，契约同步改写为 400 + ErrorEnvelope（错误码分段在
schema 描述中可见），本文件锁死该口径。
"""
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
        ctx = app.state.context
        test_client.headers.update({"X-AstroForge-Token": ctx.token})
        yield test_client


def test_validation_error_is_http_400_with_envelope(client: TestClient):
    """请求校验失败（路径参数类型不符）：HTTP 400 + 统一信封 code=1001。"""
    resp = client.post("/api/v1/tasks/some-uuid/steps/not-an-int/retry")
    assert resp.status_code == 400
    body = resp.json()
    assert set(body) == {"code", "message", "data"}
    assert body["code"] == 1001
    assert "参数校验失败" in body["message"]


def test_business_param_error_stays_http_200(client: TestClient):
    """业务级参数错误（ApiError）语义是「请求已理解但业务拒绝」，仍走 200+1001。"""
    resp = client.get("/api/v1/monitor/history", params={"range": "9h"})
    assert resp.status_code == 200
    assert resp.json()["code"] == 1001


def test_openapi_documents_400_not_422(client: TestClient):
    """契约层可见：全部 422 改写为 400 + ErrorEnvelope，且失真 schema 已移除。"""
    spec = client.get("/openapi.json").json()
    for path_item in spec["paths"].values():
        for operation in path_item.values():
            if isinstance(operation, dict):
                assert "422" not in operation.get("responses", {})
    responses = spec["paths"]["/api/v1/system/env-check"]["get"]["responses"]
    assert "400" in responses
    ref = responses["400"]["content"]["application/json"]["schema"]["$ref"]
    assert ref == "#/components/schemas/ErrorEnvelope"
    schemas = spec["components"]["schemas"]
    assert "HTTPValidationError" not in schemas
    assert "ValidationError" not in schemas
    # 错误码分段在信封 schema 描述中可见（方案 3.8）
    code_schema = schemas["ErrorEnvelope"]["properties"]["code"]
    for segment in ("0 成功", "1xxx 参数", "2xxx 服务", "3xxx 模块执行", "4xxx 资源"):
        assert segment in code_schema["description"]


def test_export_openapi_output_matches_runtime_contract(tmp_path: Path):
    """scripts/export_openapi.py 产物 == app.openapi() 运行时契约（单一事实源）。"""
    import json
    import subprocess
    import sys

    from astroforge.__main__ import load_settings_light
    from astroforge.api.app import create_app
    from astroforge.core.config_loader import REPO_ROOT

    spec = create_app(load_settings_light()).openapi()
    out = tmp_path / "openapi.json"
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "export_openapi.py"),
         "--output", str(out)],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(out.read_text(encoding="utf-8")) == spec
