# -*- coding: utf-8 -*-
"""同域 BFS 整站爬取（骨架版）。

每页仅抓取一次：正文提取与链接发现共用同一份 HTML。
完整版（Scrapling 渲染、侧边栏目录结构化、断点续爬、反爬自适应）属 Phase 2。
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

from cli_utils import fail, info, ok

PAGE_LINK_RE = re.compile(r'href="([^"#]+)"')


def crawl_site(url: str, output_dir: Path, max_pages: int = 200, interval: float = 1.0) -> dict:
    """同 host BFS：抓正文存 Markdown，返回页面清单与失败清单。"""
    import fetch

    output_dir.mkdir(parents=True, exist_ok=True)
    host = urlparse(url).netloc
    seen: set[str] = {url}
    queue = [url]
    pages: list[dict] = []
    failed: list[dict] = []

    while queue and len(seen) <= max_pages:
        current = queue.pop(0)
        try:
            html = fetch.fetch_html(current)
            text, title = fetch.html_to_md(html)
            slug = (urlparse(current).path.strip("/") or "index").replace("/", "_") or "index"
            target = output_dir / f"{slug}.md"
            target.write_text(f"# {title}\n\n> 来源: {current}\n\n{text}\n", encoding="utf-8")
            pages.append({"url": current, "path": str(target)})
            info(f"[{len(pages)}/{max_pages}] {current}")
            for href in PAGE_LINK_RE.findall(html):
                absolute = urljoin(current, href)
                parsed = urlparse(absolute)
                if parsed.netloc == host and parsed.scheme in {"http", "https"} and absolute not in seen:
                    seen.add(absolute)
                    queue.append(absolute)
        except Exception as exc:
            failed.append({"url": current, "error": str(exc)})
            print(f"[ERROR] {current}: {exc}", flush=True)
        time.sleep(max(0.0, interval))

    if pages:
        return ok({"pages": pages, "failed": failed, "count": len(pages)}, "site_crawl 完成")
    return fail(3004, "整站爬取未获得任何页面（可能被反爬拦截）", {"failed": failed})
