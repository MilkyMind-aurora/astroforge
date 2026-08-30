"""模块 CLI 共享工具：config/result JSON 读写、stdout 日志约定。

各模块独立环境运行，通过 sys.path 注入本目录复用（零第三方依赖）。
约定：结果 JSON {"code": int, "message": str, "data": {...}}；日志前缀 [INFO]/[ERROR]。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def info(msg: str) -> None:
    print(f"[INFO] {msg}", flush=True)


def error(msg: str) -> None:
    print(f"[ERROR] {msg}", flush=True)


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def save_json(path: str | Path, data: dict[str, Any]) -> None:
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"code": 0, "message": message, "data": data}


def fail(code: int, message: str, data: Any = None) -> dict[str, Any]:
    return {"code": code, "message": message, "data": data}


def add_shared_to_path() -> None:
    """把 modules/_shared 加入 sys.path（供 url_guard 等复用）。"""
    shared = Path(__file__).resolve().parent
    if str(shared) not in sys.path:
        sys.path.insert(0, str(shared))
