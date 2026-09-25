"""模块 CLI 共享工具：config/result JSON 读写、stdout 日志约定（MF3 输出收拢）。

各模块独立环境运行，通过 sys.path 注入本目录复用（零第三方依赖）。
约定：结果 JSON {"code": int, "message": str, "data": {...}}；日志前缀 [INFO]/[ERROR]。
stdout 契约【硬性】（方案 §2.5/§四）：``[INFO] ``/``[ERROR] `` 前缀行与结果 JSON
字节不变（服务核心 process_runner 逐行捕获零改动）；星幕观感（横幅/阶段/进度/
结果卡/错误卡）由 star_console 在 TTY 态渲染，管道态一律纯文本降级。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

_SHARED = Path(__file__).resolve().parent
if str(_SHARED) not in sys.path:  # cli_utils 被 CLI 以顶层模块导入，同目录 star_console 可直接复用
    sys.path.insert(0, str(_SHARED))
import star_console as _star  # noqa: E402

# 结果契约里的产物清单键（announce_result 提炼结果卡行用；各模块 data 字段同名同义）
_ITEM_LIST_KEYS = ("files", "md_files", "csv_files", "converted")
_ITEM_PATH_KEYS = ("output_path", "index_path")


def info(msg: str) -> None:
    """[INFO] 日志行（字节契约：``[INFO] {msg}\\n``，与旧 print 实现逐字节一致）。"""
    _star.log("INFO", msg)


def error(msg: str) -> None:
    """[ERROR] 日志行（服务核心按行内 ``[ERROR]`` 判定错误档，前缀契约不变）。"""
    _star.log("ERROR", msg)


def warn(msg: str) -> None:
    """[WARN] 日志行（弱警示，熔金色；服务核心捕获时按 INFO 档透传，前缀契约不变）。"""
    _star.log("WARN", msg)


def banner(module: str, detail: str = "") -> None:
    """模块横幅转发（star_console.banner；§4.1 四段式之首段）。"""
    _star.banner(module, detail)


def stage(text: str, index: int | None = None, total: int | None = None) -> None:
    """阶段分隔转发（star_console.stage；§4.1 四段式之二段）。"""
    _star.stage(text, index, total)


def progress(done: int, total: int, label: str = "进度") -> None:
    """进度条转发（star_console.progress；非 TTY 静默，进度由 [INFO] 行承担）。"""
    _star.progress(done, total, label)


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


def _result_items(data: Any) -> list[tuple[str, str]]:
    """从结果 data 提炼结果卡产物行（名称, 详情）：单路径键 + 清单键，超限折叠。"""
    if not isinstance(data, dict):
        return []
    rows: list[tuple[str, str]] = []
    for key in _ITEM_PATH_KEYS:
        value = data.get(key)
        if isinstance(value, str) and value:
            path = Path(value)
            rows.append((path.name, str(path.parent)))
    for key in _ITEM_LIST_KEYS:
        value = data.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str) and item:
                    path = Path(item)
                    rows.append((path.name, str(path.parent)))
    seen: set[tuple[str, str]] = set()
    unique = [row for row in rows if not (row in seen or seen.add(row))]
    if len(unique) > _star.ITEM_LIMIT:  # 折叠为省略行，防大产物清单刷屏
        omitted = len(unique) - _star.ITEM_LIMIT + 1
        return unique[: _star.ITEM_LIMIT - 1] + [(f"…其余 {omitted} 项", "")]
    return unique


def announce_result(result: dict[str, Any], elapsed_s: float | None = None) -> None:
    """任务收尾卡（stdout 观感层；结果 JSON 仍由 save_json 落盘，服务核心契约不变）。

    成功 → result_card（✓ 标题 + 产物摘要行 + 耗时 note）；
    失败 → 先补一条 ``[ERROR] `` 前缀行（保证服务核心日志里失败必被错误档标记，
    与既有 exception 路径的 error() 单行等价），再渲染 error_card（code + 修复指引）。
    """
    code = int(result.get("code", 0))
    data = result.get("data")
    if code == 0:
        note_parts: list[str] = []
        if isinstance(data, dict) and isinstance(data.get("count"), int):
            note_parts.append(f"{data['count']} 项")
        if elapsed_s is not None:
            note_parts.append(f"耗时 {elapsed_s:.0f}s")
        _star.result_card("任务完成", items=_result_items(data), note=" · ".join(note_parts))
        return
    _star.progress_end()  # 中途失败的进度条先收尾，避免残留 live 行
    message = str(result.get("message", "未知错误"))
    _star.log("ERROR", f"{message}（code {code}）")
    _star.error_card(code, message)


def add_shared_to_path() -> None:
    """把 modules/_shared 加入 sys.path（供 url_guard 等复用）。"""
    if str(_SHARED) not in sys.path:
        sys.path.insert(0, str(_SHARED))
