"""导出 OpenAPI 契约（双 UI 单一事实源，方案 2.4 机制 10）。

用法：python scripts/export_openapi.py --output docs/openapi.json
CI 在 ubuntu-latest 上执行并上传产物；契约变更必须重新生成 Dart 客户端。
星幕输出（MF3）：经 modules/_shared/star_console（TTY 富文本/管道纯文本）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "server"))
sys.path.insert(0, str(REPO_ROOT / "modules" / "_shared"))
from star_console import banner, log  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="导出 Sidereal Core OpenAPI 契约")
    parser.add_argument("--output", default=str(REPO_ROOT / "docs" / "openapi.json"))
    args = parser.parse_args()
    banner("export_openapi", "OpenAPI 契约导出 · Sidereal Core")

    from astroforge.__main__ import load_settings_light
    from astroforge.api.app import create_app

    app = create_app(load_settings_light())
    spec = app.openapi()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    log(None, f"OpenAPI 契约已导出: {output}（{len(spec.get('paths', {}))} 个路径）")
    log(None, "提示：契约变更后需用 openapi_generator 重新生成 Dart 客户端（app/lib/data/api_client/）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
