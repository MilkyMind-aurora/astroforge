"""文件路由：白名单目录浏览 / 文本预览 / 流式下载（方案 3.8 files API）。"""
from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import FileResponse

from astroforge.api import deps
from astroforge.api.response import ok
from astroforge.utils.file_utils import ensure_text_previewable, resolve_in_whitelist

router = APIRouter(prefix="/files", tags=["files"])


def _whitelist_roots(ctx: deps.AppContext) -> list:
    data_dir = ctx.settings.data_dir()
    return [data_dir, ctx.settings.template_dir(), data_dir / "raw", data_dir / "output"]


@router.get("/browse", dependencies=[deps.TokenDep])
async def browse(ctx: deps.CtxDep, path: str = Query(default="")) -> dict:
    target = resolve_in_whitelist(path or str(ctx.settings.data_dir()), _whitelist_roots(ctx))
    if not target.exists():
        return ok({"path": str(target), "exists": False, "dirs": [], "files": []})
    dirs, files = [], []
    for entry in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if entry.is_dir():
            dirs.append({"name": entry.name, "path": str(entry)})
        else:
            files.append({
                "name": entry.name, "path": str(entry),
                "size_bytes": entry.stat().st_size,
                "suffix": entry.suffix.lower(),
            })
    return ok({"path": str(target), "exists": True, "dirs": dirs, "files": files})


@router.get("/preview", dependencies=[deps.TokenDep])
async def preview(ctx: deps.CtxDep, path: str = Query()) -> dict:
    target = resolve_in_whitelist(path, _whitelist_roots(ctx))
    ensure_text_previewable(target)
    content = target.read_text(encoding="utf-8", errors="replace")
    return ok({"path": str(target), "suffix": target.suffix.lower(),
               "size_bytes": target.stat().st_size, "content": content[:1_000_000]})


@router.get("/download", dependencies=[deps.TokenDep])
async def download(ctx: deps.CtxDep, path: str = Query()) -> FileResponse:
    target = resolve_in_whitelist(path, _whitelist_roots(ctx))
    if not target.is_file():
        from astroforge.api.response import ApiError, ErrorCode

        raise ApiError(ErrorCode.FILE_NOT_FOUND, f"文件不存在: {path}")
    # FileResponse 分块流式传输，避免大文件占用内存（方案风险表措施）
    return FileResponse(target, filename=target.name, media_type="application/octet-stream")
