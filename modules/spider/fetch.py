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


class _MarkdownExtractor(HTMLParser):
    """结构化正文提取（方案 2.1.2）：HTML → Markdown。

    支持：标题层级(#~######)、段落、有序/无序列表、代码块(```)、
    行内链接 [text](绝对URL)、引用块；跳过 script/style/noscript。
    """

    SKIP = ("script", "style", "noscript", "template", "iframe", "svg")
    BLOCK_TAGS = {"p", "div", "section", "article", "li", "tr", "br", "blockquote"}

    def __init__(self, base_url: str = "") -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skip_depth = 0
        self._lines: list[str] = []
        self._buf: list[str] = []
        self._code: list[str] | None = None
        self._list_stack: list[str] = []  # "ul" | "ol"
        self._quote_depth = 0
        self._href_stack: list[str] = []
        self._base = base_url

    # ---- 行缓冲工具 ----
    def _flush_buf(self) -> None:
        text = "".join(self._buf).strip()
        self._buf = []
        if not text:
            return
        if self._code is not None:
            self._code.append(text)
            return
        prefix = ""
        if self._quote_depth:
            prefix = "> " * self._quote_depth
        if self._list_stack:
            marker = "-" if self._list_stack[-1] == "ul" else "1."
            prefix += f"{marker} "
        self._lines.append(prefix + text)

    def _newline(self) -> None:
        self._flush_buf()
        if self._lines and self._lines[-1] != "":
            self._lines.append("")

    # ---- 解析事件 ----
    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[name-defined]
        if tag == "title":
            self._in_title = True
        if tag in self.SKIP:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        href = dict(attrs).get("href")
        if tag == "a" and href:
            self._flush_buf()
            self._href_stack.append((len(self._buf), urljoin(self._base, href) if self._base else href))
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._flush_buf()
            self._newline()
            self._buf.append("#" * int(tag[1]) + " ")
        elif tag == "pre":
            self._flush_buf()
            self._newline()
            self._code = []
        elif tag == "ul":
            self._flush_buf()
            self._list_stack.append("ul")
        elif tag == "ol":
            self._flush_buf()
            self._list_stack.append("ol")
        elif tag == "blockquote":
            self._flush_buf()
            self._quote_depth += 1
        elif tag == "br":
            self._buf.append("\n")
        elif tag == "code" and self._code is None:
            self._buf.append("`")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in self.SKIP and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag == "a" and self._href_stack:
            start, href = self._href_stack.pop()
            # 把 <a>…</a> 之间的缓冲片段包装为 [text](href)（留在缓冲里随行输出）
            link_text = "".join(self._buf[start:]).strip() or href
            del self._buf[start:]
            self._buf.append(f"[{link_text}]({href})")
        elif tag == "code" and self._code is None:
            self._buf.append("`")
        elif tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self._flush_buf()
            self._newline()
        elif tag == "pre" and self._code is not None:
            self._lines.append("```")
            self._lines.extend(self._code)
            self._lines.append("```")
            self._code = None
            self._newline()
        elif tag in {"ul", "ol"} and self._list_stack:
            self._flush_buf()
            self._list_stack.pop()
        elif tag == "blockquote" and self._quote_depth:
            self._flush_buf()
            self._quote_depth -= 1
        elif tag in self.BLOCK_TAGS:
            self._flush_buf()
            if tag in {"p", "div", "section", "article", "blockquote"}:
                self._newline()

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data
            return
        if self._skip_depth:
            return
        if self._code is not None:
            self._code.append(data.rstrip("\n"))
            return
        if data.strip():
            self._buf.append(data if data.strip() else " ")

    def result(self) -> tuple[str, str]:
        self._flush_buf()
        text = "\n".join(line for line in self._lines)
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        return text, self.title.strip()


def _http_get(url: str, timeout: int = 30) -> str:
    url = validate_external_url(url)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _OPENER.open(request, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _scrapling_get(url: str, browser: dict | None) -> str:
    """经 browser_launcher 用本地 Chromium 渲染抓取（scrapling 0.4.x 会话参数）。"""
    import browser_launcher

    return browser_launcher.render_fetch(url, browser or {})


def fetch_html(url: str, browser: dict | None = None) -> str:
    """抓取原始 HTML：browser 配置存在且 Scrapling 可用时走渲染路径，
    否则回退 urllib（两者均经外联校验与受限重定向）。"""
    url = validate_external_url(url)
    if browser and SCRAPLING_AVAILABLE:  # pragma: no cover（视 env 而定）
        try:
            return _scrapling_get(url, browser)
        except Exception as exc:  # 渲染失败回退静态抓取
            print(f"[WARN] Scrapling 渲染失败，回退 urllib: {exc}", flush=True)
    return _http_get(url)


def html_to_md(html: str, base_url: str = "") -> tuple[str, str]:
    """从 HTML 提取 (结构化 Markdown, 标题)；base_url 用于链接绝对化。"""
    parser = _MarkdownExtractor(base_url)
    parser.feed(html)
    text, title = parser.result()
    return text, title or ""


def fetch_page_text(url: str, browser: dict | None = None) -> tuple[str, str]:
    """返回 (结构化 Markdown, 标题)；browser 配置存在时走渲染路径。"""
    url = validate_external_url(url)
    if browser and SCRAPLING_AVAILABLE:  # pragma: no cover（视 env 而定）
        try:
            html = _scrapling_get(url, browser)
        except Exception:
            html = _http_get(url)
    else:
        html = _http_get(url)
    text, title = html_to_md(html, url)
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
