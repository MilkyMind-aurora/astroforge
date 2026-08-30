# -*- coding: utf-8 -*-
"""同域整站爬取：侧边栏结构化模式 + BFS 回落（Phase 2 Task 2.1.4 / 2.3）。

structured 模式：入口页先跑 sidebar_parser 解析导航目录；解析出章节结构则按
「一级章节一个子目录、每页一个 md」输出，并在 output_dir 写 _index.json。
断点续爬（2.1.5）：output_dir/.crawl_state.json 记录 completed/failed；
resume=True（默认）重跑时跳过已完成页面、重试失败页面。
两条路径共用限速（interval）、去重（seen）与失败清单逻辑；所有请求一律
经 fetch.fetch_html（内置 url_guard 外联校验 + 受限重定向）。
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import sidebar_parser
from cli_utils import fail, info, ok
from url_guard import UrlGuardError

PAGE_LINK_RE = re.compile(r'href="([^"#]+)"')

# 目录/文件名 slug 最大长度（超长截断，避免 Windows 路径超限）
_SLUG_MAX_LEN = 60


def slugify(text: str, fallback: str = "untitled") -> str:
    """标题 slug 化：保留中英文/数字/下划线，空白与其余符号折叠为连字符。

    Python re 的 \\w 对 str 默认匹配 Unicode 词字符（含中文），因此中文
    章节名直接保留可读形式；全空结果退回 fallback。
    """
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"[^\w-]+", "-", text, flags=re.UNICODE)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text[:_SLUG_MAX_LEN].strip("-") or fallback


def _norm_url(url: str) -> str:
    """去掉 #fragment 的规范化 URL（用于去重与入队）。"""
    return urldefrag(url or "")[0]


# ---- 断点续爬状态（2.1.5）：output_dir/.crawl_state.json ----

def _load_state(output_dir: Path) -> dict:
    state_path = output_dir / ".crawl_state.json"
    if not state_path.exists():
        return {"completed": [], "failed": {}}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        return {
            "completed": list(state.get("completed", [])),
            "failed": dict(state.get("failed", {})),
        }
    except (json.JSONDecodeError, OSError):
        return {"completed": [], "failed": {}}


def _save_state(output_dir: Path, completed: set[str], failed: dict[str, str]) -> None:
    state_path = output_dir / ".crawl_state.json"
    state_path.write_text(json.dumps({
        "completed": sorted(completed),
        "failed": failed,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def _page_stem(page_url: str, title: str) -> str:
    """页面文件名：优先 URL 路径名（稳定且唯一），为空退回标题 slug。"""
    stem = Path(urlparse(page_url).path).stem
    return slugify(stem, fallback="") or slugify(title, fallback="page")


def _write_structured_page(chapter_dir: Path, page_url: str, title: str,
                           text: str, used_stems: dict[Path, set[str]]) -> Path:
    """在章节子目录写入一页 Markdown，文件名撞名时追加序号。"""
    chapter_dir.mkdir(parents=True, exist_ok=True)
    taken = used_stems.setdefault(chapter_dir, set())
    stem, n = _page_stem(page_url, title), 1
    candidate = stem
    while candidate in taken:
        n += 1
        candidate = f"{stem}-{n}"
    taken.add(candidate)
    target = chapter_dir / f"{candidate}.md"
    target.write_text(f"# {title}\n\n> 来源: {page_url}\n\n{text}\n", encoding="utf-8")
    return target


def crawl_site(url: str, output_dir: Path, max_pages: int = 200, interval: float = 1.0,
               structured: bool = True, resume: bool = True) -> dict:
    """整站爬取入口：先试侧边栏结构化，解析不到目录则回落同域 BFS。

    resume=True 时加载 .crawl_state.json：已完成页面跳过、失败页面重试。
    返回 {"code": 0, "data": {...}} 或 {"code": 3004, ...}（反爬拦截/零页面）。
    """
    import fetch  # 延迟导入：单测 monkeypatch fetch.fetch_html 生效

    output_dir.mkdir(parents=True, exist_ok=True)
    state = _load_state(output_dir) if resume else {"completed": [], "failed": {}}
    resumed = bool(state["completed"])

    if structured:
        try:
            entry_html = fetch.fetch_html(url)
        except UrlGuardError:
            raise  # URL 安全校验问题交由上层 CLI 归类（1002），不伪装成反爬
        except Exception as exc:
            return fail(3004, f"入口页抓取失败（可能被反爬拦截）: {exc}",
                        {"mode": "structured",
                         "failed": [{"url": url, "error": str(exc)}]})
        result = _crawl_structured(url, entry_html, output_dir, max_pages, interval,
                                   fetch, state)
        if result is not None:
            if resumed:
                result["data"]["resumed"] = True
            return result
        info("未解析到侧边栏目录，回落同域 BFS 爬取")
        return _crawl_bfs(url, output_dir, max_pages, interval, fetch,
                          fallback=True, state=state, entry_html=entry_html)

    return _crawl_bfs(url, output_dir, max_pages, interval, fetch, state=state)


def _crawl_structured(url: str, entry_html: str, output_dir: Path,
                      max_pages: int, interval: float, fetch,
                      state: dict) -> dict | None:
    """侧边栏结构化爬取；解析不到目录时返回 None（调用方回落 BFS）。"""
    items = sidebar_parser.parse_sidebar(entry_html, url)
    if not items:
        return None
    groups = sidebar_parser.group_by_top_level(items)
    host = urlparse(url).netloc
    entry = _norm_url(url)
    completed: set[str] = set(state.get("completed", []))
    failed_state: dict[str, str] = dict(state.get("failed", {}))

    # 章节子目录：按侧边栏顺序编号，保证目录树与文档顺序一致
    chapter_dirs: dict[str, Path] = {}
    for ordinal, chapter in enumerate(groups, start=1):
        slug = slugify(chapter, fallback="chapter")
        chapter_dirs[chapter] = output_dir / f"{ordinal:02d}-{slug}"

    # 抓取队列：按侧边栏顺序展开；仅同域 http(s) 链接入队（外链只记录不抓取）
    queue: list[tuple[str, str]] = []
    seen: set[str] = set()
    for chapter, page_items in groups.items():
        for page in page_items:
            target = _norm_url(page.get("url") or "")
            if not target or urlparse(target).scheme not in ("http", "https"):
                continue
            if urlparse(target).netloc != host or target in seen:
                continue
            seen.add(target)
            queue.append((target, chapter))
    # 入口页不在侧边栏清单时（如指向章节锚点页），补到队首归入首个章节
    if entry not in seen:
        queue.insert(0, (entry, next(iter(groups), sidebar_parser.UNGROUPED_KEY)))
        seen.add(entry)
    # 断点续爬：已完成页面跳过（失败的留在队列里等重试）
    skipped = sum(1 for target, _ in queue[:max_pages] if target in completed)
    queue = [(t, c) for t, c in queue[:max_pages] if t not in completed]

    pages: list[dict] = []
    failed: list[dict] = []
    used_stems: dict[Path, set[str]] = {}
    total = len(queue)
    for index, (target, chapter) in enumerate(queue, start=1):
        try:
            # 入口页复用已抓取的 HTML，省一次请求
            page_html = entry_html if target == entry else fetch.fetch_html(target)
            text, title = fetch.html_to_md(page_html, base_url=target)
            path = _write_structured_page(chapter_dirs[chapter], target, title, text, used_stems)
            pages.append({"url": target, "path": str(path), "chapter": chapter, "title": title})
            completed.add(target)
            failed_state.pop(target, None)
            _save_state(output_dir, completed, failed_state)
            info(f"[{index}/{total}] {target}")
        except Exception as exc:
            failed.append({"url": target, "chapter": chapter, "error": str(exc)})
            failed_state[target] = str(exc)
            _save_state(output_dir, completed, failed_state)
            print(f"[ERROR] {target}: {exc}", flush=True)
        time.sleep(max(0.0, interval))

    # _index.json：完整侧边栏结构 + 页面清单 + 失败清单
    index_path = output_dir / "_index.json"
    index_path.write_text(json.dumps({
        "mode": "structured",
        "entry_url": url,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "max_pages": max_pages,
        "request_interval": interval,
        "sidebar": groups,
        "pages": pages,
        "failed": failed,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    data = {"pages": pages, "failed": failed, "count": len(pages),
            "mode": "structured", "chapters": list(groups),
            "index_path": str(index_path)}
    if resumed := bool(state.get("completed")):
        data["resumed"] = resumed
        data["skipped_completed"] = skipped
    if pages:
        return ok(data, "site_crawl 完成（侧边栏结构化模式）")
    return fail(3004, "整站爬取未获得任何页面（可能被反爬拦截）", data)


def _crawl_bfs(url: str, output_dir: Path, max_pages: int, interval: float,
               fetch, fallback: bool = False,
               state: dict | None = None, entry_html: str | None = None) -> dict:
    """同 host BFS 骨干：抓正文存 Markdown；fallback=True 时在 data 注明回落。"""
    completed: set[str] = set((state or {}).get("completed", []))
    failed_state: dict[str, str] = dict((state or {}).get("failed", {}))
    host = urlparse(url).netloc
    entry = _norm_url(url)
    seen: set[str] = {entry}
    queue = [entry]
    pages: list[dict] = []
    failed: list[dict] = []

    while queue and len(seen) <= max_pages:
        current = queue.pop(0)
        if current in completed and current != entry:
            pages.append({"url": current, "path": "", "skipped": True})
            continue
        try:
            # 入口页复用已抓取的 HTML（structured 回落时省一次请求）
            html = entry_html if (current == entry and entry_html is not None) \
                else fetch.fetch_html(current)
            text, title = fetch.html_to_md(html, base_url=current)
            slug = (urlparse(current).path.strip("/") or "index").replace("/", "_") or "index"
            target = output_dir / f"{slug}.md"
            target.write_text(f"# {title}\n\n> 来源: {current}\n\n{text}\n", encoding="utf-8")
            pages.append({"url": current, "path": str(target)})
            completed.add(current)
            failed_state.pop(current, None)
            _save_state(output_dir, completed, failed_state)
            info(f"[{len(pages)}/{max_pages}] {current}")
            for href in PAGE_LINK_RE.findall(html):
                absolute = urljoin(current, href)
                parsed = urlparse(absolute)
                if parsed.netloc == host and parsed.scheme in {"http", "https"} and absolute not in seen:
                    seen.add(absolute)
                    queue.append(absolute)
        except Exception as exc:
            failed.append({"url": current, "error": str(exc)})
            failed_state[current] = str(exc)
            _save_state(output_dir, completed, failed_state)
            print(f"[ERROR] {current}: {exc}", flush=True)
        time.sleep(max(0.0, interval))

    data: dict = {"pages": pages, "failed": failed, "count": len(pages), "mode": "bfs"}
    if fallback:
        data["fallback_bfs"] = True
    if pages:
        return ok(data, "site_crawl 完成")
    return fail(3004, "整站爬取未获得任何页面（可能被反爬拦截）", data)
