"""统一响应信封与错误码分段（方案 3.8）。

0 成功 | 1xxx 参数 | 2xxx 服务 | 3xxx 模块执行 | 4xxx 资源
"""
from __future__ import annotations

from typing import Any


class ErrorCode:
    OK = 0
    MISSING_PARAM = 1001
    INVALID_PATH = 1002
    INVALID_TEMPLATE = 1003
    YAML_INVALID = 1004
    UNAUTHORIZED = 2001
    INTERNAL = 2002
    CONFIG_MISSING = 2003
    DB_UNAVAILABLE = 2004
    ENV_MISSING = 3001
    PROC_TIMEOUT = 3002
    MODULE_CRASH = 3003
    CRAWLER_BLOCKED = 3004
    MODEL_LOAD_FAILED = 3005
    NOT_IMPLEMENTED = 3006
    FILE_NOT_FOUND = 4001
    MEMORY_LIMIT = 4002
    DISK_FULL = 4003
    AI_ENGINE_UNREACHABLE = 4004


class ApiError(Exception):
    """业务异常：由全局异常处理器转为统一信封。"""

    def __init__(self, code: int, message: str, data: Any = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


def ok(data: Any = None, message: str = "ok") -> dict[str, Any]:
    return {"code": ErrorCode.OK, "message": message, "data": data}


def fail(code: int, message: str, data: Any = None) -> dict[str, Any]:
    return {"code": code, "message": message, "data": data}
