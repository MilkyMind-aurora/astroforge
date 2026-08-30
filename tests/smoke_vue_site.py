# -*- coding: utf-8 -*-
"""真站冒烟脚本：cn.vuejs.org 结构化爬取（手动运行，不进 pytest 收集）。

用法：./.venv/Scripts/python tests/smoke_vue_site.py
产物：data/cache/vue_smoke/（章节目录树 + _index.json）
      data/cache/vue_smoke_result.json（结果 JSON 摘要）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # Windows 控制台非 UTF-8 兜底
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT / "modules" / "_shared", ROOT / "modules" / "spider"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import site_crawl  # noqa: E402
from cli_utils import save_json  # noqa: E402


def main() -> int:
    out_dir = ROOT / "data" / "cache" / "vue_smoke"
    result = site_crawl.crawl_site(
        "https://cn.vuejs.org/guide/introduction.html",
        output_dir=out_dir,
        max_pages=15,
        interval=1.0,
        structured=True,
    )
    save_json(ROOT / "data" / "cache" / "vue_smoke_result.json", result)

    data = result.get("data") or {}
    summary = {
        "code": result["code"],
        "message": result["message"],
        "mode": data.get("mode"),
        "fallback_bfs": data.get("fallback_bfs"),
        "chapters": data.get("chapters"),
        "count": data.get("count"),
        "success": [p["url"] for p in data.get("pages", [])],
        "failed": data.get("failed", []),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # 输出目录树概览
    if out_dir.is_dir():
        for path in sorted(out_dir.rglob("*")):
            rel = path.relative_to(out_dir)
            print(("目录 " if path.is_dir() else "  md ") + str(rel))
    return 0 if result["code"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
