"""采集层 CLI 入口（env_spider）。

约定：python cli.py --config <config.json> --output <result.json>
task_type: spider_single | spider_site | spider_pdf | spider_table
URL 一律先经 url_guard 外联安全校验（仅允许 http/https）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
import fetch  # 同目录模块
import site_crawl
from cli_utils import error, fail, info, load_json, ok, save_json
from url_guard import UrlGuardError, validate_external_url


def run_single(cfg: dict) -> dict:
    url = validate_external_url(cfg.get("url"))
    output_dir = Path(cfg.get("output_dir", "output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "single_page.md"
    text, title = fetch.fetch_page_text(url, browser=cfg.get("browser"))
    md = f"# {title}\n\n{text}\n"
    output_path.write_text(md, encoding="utf-8")
    info(f"单页抓取完成: {output_path}")
    return ok({"output_path": str(output_path), "title": title}, "single_page 完成")


def run_site(cfg: dict) -> dict:
    url = validate_external_url(cfg.get("url"))
    return site_crawl.crawl_site(
        url,
        output_dir=Path(cfg.get("output_dir", "output/site")),
        max_pages=int(cfg.get("max_pages", 200)),
        interval=float(cfg.get("request_interval", 1.0)),
        # 结构化侧边栏模式默认开启；cfg["structured"]=false 时走纯 BFS
        structured=bool(cfg.get("structured", True)),
        # 断点续爬默认开启；cfg["resume"]=false 强制全量重爬
        resume=bool(cfg.get("resume", True)),
        # browser 配置存在时经 Scrapling/本地 Chromium 渲染抓取
        browser=cfg.get("browser"),
    )


def run_pdf(cfg: dict) -> dict:
    url = validate_external_url(cfg.get("url"))
    output_dir = Path(cfg.get("output_dir", "output/pdf"))
    output_dir.mkdir(parents=True, exist_ok=True)
    retry = int(cfg.get("auto_retry", 3))
    saved = fetch.download_pdfs_from_page(url, output_dir, retry=retry)
    return ok({"files": saved, "count": len(saved)}, "pdf_download 完成")


def run_table(cfg: dict) -> dict:
    # 诚实降级：结构化表格爬取属 Phase 2（Scrapling 适配 + XHR 捕获）
    return fail(3006, "表格爬取属 Phase 2 开发中（spider_table）", {"url": cfg.get("url")})


def main() -> int:
    parser = argparse.ArgumentParser(description="AstroForge 采集模块（Scrapling/回退 urllib）")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    cfg = load_json(args.config)
    task_type = cfg.get("task_type")
    handlers = {
        "spider_single": run_single,
        "spider_site": run_site,
        "spider_pdf": run_pdf,
        "spider_table": run_table,
    }
    if task_type not in handlers:
        result = fail(1001, f"缺少或未知 task_type: {task_type}")
    elif not cfg.get("url"):
        result = fail(1001, "缺少 url 参数")
    else:
        try:
            result = handlers[task_type](cfg)
        except UrlGuardError as exc:
            result = fail(1002, f"URL 未通过安全校验: {exc}")
        except Exception as exc:  # 模块崩溃不裸奔，统一转结果 JSON
            error(f"执行异常: {exc}")
            result = fail(3003, f"模块执行异常: {exc}")
    save_json(args.output, result)
    return 0 if result["code"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
