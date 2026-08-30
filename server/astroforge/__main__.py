"""AstroForge Sidereal Core 命令入口。

python -m astroforge serve            前台启动服务核心
python -m astroforge serve --daemon   守护启动（Windows pythonw / macOS nohup 由脚本处理）
python -m astroforge doctor           环境自检
python -m astroforge export-openapi   导出 OpenAPI 契约
"""
from __future__ import annotations

import argparse
import asyncio
import sys


def _cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from astroforge.api.app import create_app
    from astroforge.core.config_loader import load_settings

    settings = load_settings()
    app = create_app(settings)
    config = uvicorn.Config(
        app, host=args.host or settings.service.host, port=args.port or settings.service.port,
        log_level="info", workers=1,  # 固定单 worker：任务状态在进程内（方案补丁 6）
    )
    server = uvicorn.Server(config)

    async def _serve() -> None:
        serve_task = asyncio.create_task(server.serve())
        # 等待 lifespan 装配完成后再启用停机看护
        while not hasattr(app.state, "context"):
            await asyncio.sleep(0.1)
        shutdown_task = asyncio.create_task(_watch_shutdown(server, app.state.context))
        await serve_task
        shutdown_task.cancel()

    asyncio.run(_serve())
    return 0


async def _watch_shutdown(server, ctx) -> None:
    """看护循环：优雅停机请求置位 uvicorn.should_exit（方案补丁 6）。"""
    while not ctx.shutdown_requested:
        await asyncio.sleep(0.5)
    server.should_exit = True


def _cmd_doctor(_args: argparse.Namespace) -> int:
    from astroforge.core.config_loader import load_settings
    from astroforge.core.env_manager import run_env_check

    settings = load_settings()
    summary = asyncio.run(run_env_check(settings))
    print(f"AstroForge Sidereal Core 环境体检：{summary['ok_count']}/{summary['total']} 通过")
    for item in summary["items"]:
        mark = "✅" if item["ok"] else "❌"
        print(f" {mark} {item['name']}: {item['detail']}")
    return 0 if summary["ok_count"] == summary["total"] else 1


def _cmd_export_openapi(args: argparse.Namespace) -> int:
    import json
    from pathlib import Path

    from astroforge.api.app import create_app

    app = create_app(load_settings_light())
    spec = app.openapi()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OpenAPI 契约已导出: {output}（{len(spec.get('paths', {}))} 个路径）")
    return 0


def load_settings_light():
    """导出契约时不需要真实数据库密码，跳过密码校验。"""
    from astroforge.core import config_loader

    try:
        return config_loader.load_settings()
    except RuntimeError:
        settings = config_loader.Settings()
        settings.config_path = str(config_loader.DEFAULT_CONFIG)
        return settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="astroforge", description="AstroForge Sidereal Core 服务核心")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="启动服务核心（127.0.0.1:8420）")
    serve.add_argument("--host", default=None)
    serve.add_argument("--port", type=int, default=None)
    serve.add_argument("--daemon", action="store_true", help="守护模式（由启动脚本配合 pythonw/nohup 使用）")
    serve.set_defaults(func=_cmd_serve)

    doctor = sub.add_parser("doctor", help="环境自检")
    doctor.set_defaults(func=_cmd_doctor)

    export = sub.add_parser("export-openapi", help="导出 OpenAPI 契约")
    export.add_argument("--output", default="docs/openapi.json")
    export.set_defaults(func=_cmd_export_openapi)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
