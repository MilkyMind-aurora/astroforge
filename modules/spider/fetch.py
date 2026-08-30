# -*- coding: utf-8 -*-
"""页面抓取与 PDF 下载（骨架版：优先 Scrapling，缺失回退 urllib）。

安全约定（Mimosa 约束）：所有请求汇点（urlopen / Scrapling get / 重定向目标）
一律先经 url_guard 校验——仅允许 http/https，拒绝 localhost、环回、私有与保留
地址；重定向目标逐跳复检，防 DNS rebinding。
完整 Scrapling/StealthyFetcher 版本属 Phase 2（侧边栏结构化、反爬适配）。
"""
from __future__ import annotations

import re
import sys
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "_shared"))
from url_guard import validate_external_url  # noqa: E402

try:  # Scrapling 存在则优先（env_spider）
    from scrapling import Fetcher as _ScraplingFetcher  # type: ignore

    SCRAPLING_AVAILABLE = True
except Exception:  # pragma: no cover
    _ScraplingFetcher = None
    SCRAPLING_AVAILABLE = False

USER_AGENT = "Mozilla/5.0 (compatible; AstroForgeSpider/0.1; +local)"


class _GuardedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """重定向逐跳复检：每一跳目标重新过外联守卫。"""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        validate_external_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_GuardedRedirectHandler)


class _TextExtractor(HTMLParser):
    """最小正文提取：title + 跳过 script/style 的可见文本。"""

    SKIP = ("script", "style", "noscript", "head")

    def __init__(self) -> None:
        super().__init__()
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self.chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[name-defined]
        if tag == "title":
            self._in_title = True
        if tag in self.SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in self.SKIP and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
        elif self._skip_depth == 0 and data.strip():
            self.chunks.append(data.strip())


def _http_get(url: str, timeout: int = 30) -> str:
    url = validate_external_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _OPENER.open(request, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_html(url: str) -> str:
    """抓取原始 HTML（Scrapling 优先，回退 urllib）。"""
    url = validate_external_url(url)
    if SCRAPLING_AVAILABLE:  # pragma: no cover（视 env 而定）
        return _ScraplingFetcher().get(url).html_content
    return _http_get(url)


def html_to_md(html: str) -> tuple[str, str]:
    """从 HTML 提取 (正文文本, 标题)。"""
    parser = _TextExtractor()
    parser.feed(html)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(parser.chunks))
    return text, parser.title.strip()


def fetch_page_text(url: str) -> tuple[str, str]:
    """返回 (正文文本, 标题)。"""
    url = validate_external_url(url)
    if SCRAPLING_AVAILABLE:  # pragma: no cover（视 env 而定）
        page = _ScraplingFetcher().get(url)
        title = page.css_first("title::text") or url
        body = "\n".join(p.strip() for p in page.css("p::text") if p.strip())
        return body or title, title
    text, title = html_to_md(_http_get(url))
    return text, title or url


PDF_LINK_RE = re.compile(r'href="([^"]+\.pdf)"', re.IGNORECASE)


def download_pdfs_from_page(url: str, output_dir: Path, retry: int = 3) -> list[str]:
    """抓取页面上的 .pdf 链接并流式下载（带重试）。"""
    html = _http_get(url)
    # urljoin 对绝对链接原样返回，相对链接基于当前页拼接
    links = [urljoin(url, href) for href in PDF_LINK_RE.findall(html)]
    saved: list[str] = []
    for link in links:
        link = validate_external_url(link)  # 每个 PDF 请求点独立校验
        name = Path(urlparse(link).path).name or "download.pdf"
        target = output_dir / name
        for attempt in range(1, retry + 1):
            try:
                request = urllib.request.Request(link, headers={"User-Agent": USER_AGENT})
                with _OPENER.open(request, timeout=60) as resp, target.open("wb") as fh:
                    while chunk := resp.read(1024 * 256):
                        fh.write(chunk)
                saved.append(str(target))
                print(f"[INFO] 已下载: {name}", flush=True)
                break
            except Exception as exc:
                print(f"[ERROR] {link} 第 {attempt} 次失败: {exc}", flush=True)
                time.sleep(1.5 * attempt)
    return saved
