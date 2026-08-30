"""页面抓取与 PDF 下载（骨架版：优先 Scrapling，缺失回退 urllib+html.parser）。

完整 Scrapling/StealthyFetcher 版本属 Phase 2（侧边栏结构化、反爬适配）。
"""
from __future__ import annotations

import re
import time
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse

try:  # Scrapling 存在则优先（env_spider）
    from scrapling import Fetcher as _ScraplingFetcher  # type: ignore

    SCRAPLING_AVAILABLE = True
except Exception:  # pragma: no cover
    _ScraplingFetcher = None
    SCRAPLING_AVAILABLE = False

USER_AGENT = "Mozilla/5.0 (compatible; AstroForgeSpider/0.1; +local)"


class _TextExtractor(HTMLParser):
    """最小正文提取：title + 跳过 script/style 的可见文本。"""

    SKIP = {"script", "style", "noscript", "head"}

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
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def fetch_page_text(url: str) -> tuple[str, str]:
    """返回 (正文文本, 标题)。优先 Scrapling。"""
    if SCRAPLING_AVAILABLE:  # pragma: no cover（视 env 而定）
        page = _ScraplingFetcher().get(url)
        title = page.css_first("title::text") or url
        body = "\n".join(p.strip() for p in page.css("p::text") if p.strip())
        return body or title, title
    html = _http_get(url)
    parser = _TextExtractor()
    parser.feed(html)
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(parser.chunks))
    return text, parser.title.strip() or url


PDF_LINK_RE = re.compile(r'href="([^"]+\.pdf)"', re.IGNORECASE)


def download_pdfs_from_page(url: str, output_dir: Path, retry: int = 3) -> list[str]:
    """抓取页面上的 .pdf 链接并流式下载（带重试）。"""
    html = _http_get(url)
    # urljoin 对绝对链接原样返回，相对链接基于当前页拼接
    links = [urljoin(url, href) for href in PDF_LINK_RE.findall(html)]
    saved: list[str] = []
    for link in links:
        name = Path(urlparse(link).path).name or "download.pdf"
        target = output_dir / name
        for attempt in range(1, retry + 1):
            try:
                request = urllib.request.Request(link, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(request, timeout=60) as resp, target.open("wb") as fh:
                    while chunk := resp.read(1024 * 256):
                        fh.write(chunk)
                saved.append(str(target))
                print(f"[INFO] 已下载: {name}", flush=True)
                break
            except Exception as exc:
                print(f"[ERROR] {link} 第 {attempt} 次失败: {exc}", flush=True)
                time.sleep(1.5 * attempt)
    return saved
