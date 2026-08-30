"""文件安全访问：路径白名单 + 类型/大小限制（方案 3.8 files API 依据）。"""
from __future__ import annotations

from pathlib import Path

from astroforge.api.response import ApiError, ErrorCode

TEXT_EXTENSIONS = {".md", ".txt", ".log", ".json", ".yaml", ".yml", ".csv", ".py", ".toml", ".ini"}
PREVIEW_MAX_BYTES = 5 * 1024 * 1024  # 文本预览 ≤ 5MB（方案 3.8）


def resolve_in_whitelist(path_str: str, roots: list[Path]) -> Path:
    """把请求路径解析并校验必须落在白名单根目录内，防目录穿越。"""
    if not path_str:
        raise ApiError(ErrorCode.MISSING_PARAM, "缺少路径参数")
    try:
        target = Path(path_str).expanduser().resolve()
    except (OSError, ValueError) as exc:
        raise ApiError(ErrorCode.INVALID_PATH, f"非法路径: {path_str}") from exc
    for root in roots:
        try:
            target.relative_to(root.resolve())
            return target
        except ValueError:
            continue
    raise ApiError(ErrorCode.INVALID_PATH, f"路径超出白名单范围: {path_str}")


def ensure_text_previewable(path: Path) -> None:
    if not path.is_file():
        raise ApiError(ErrorCode.FILE_NOT_FOUND, f"文件不存在: {path}")
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        raise ApiError(ErrorCode.INVALID_PATH, f"不支持的预览类型: {path.suffix}")
    if path.stat().st_size > PREVIEW_MAX_BYTES:
        raise ApiError(ErrorCode.INVALID_PATH, "文件超过预览大小上限（5MB），请用下载")
