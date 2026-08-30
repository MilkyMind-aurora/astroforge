# -*- coding: utf-8 -*-
"""Vue 官方文档结构化爬取测试（Phase 2 Task 2.1.3/2.1.4）。

离线用例：parse_sidebar / group_by_top_level / crawl_site(structured) 全部
基于内置 Vue 风格 HTML 片段（对照 cn.vuejs.org 实际 VitePress 结构简化），
不出网、不落仓库数据目录（输出到 pytest tmp_path）。
网络用例：默认跳过；设置环境变量 ASTROFORGE_NETWORK_TEST=1 后才真实请求
cn.vuejs.org 做冒烟验证。
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

if hasattr(sys.stdout, "reconfigure"):  # Windows 控制台非 UTF-8 兜底
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
for _path in (REPO_ROOT / "modules" / "_shared", REPO_ROOT / "modules" / "spider"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import fetch  # noqa: E402
import sidebar_parser  # noqa: E402
import site_crawl  # noqa: E402

BASE = "https://cn.vuejs.org/guide/introduction.html"

# Vue 风格侧边栏片段：aside.VPSidebar > nav > div.group > section.VPSidebarGroup
# 章节标题 = div.title > h2.title-text；页面链接 = a.link > p.link-text
# 顶部 nav 带 menu 类名（应被排除）；含一个跨域外链（仅记录不抓取）
SIDEBAR_HTML = """<html><head><title>简介 | Vue.js</title></head><body>
<nav class="VPNavBarMenu menu"><a href="/">首页</a></nav>
<aside class="VPSidebar">
  <nav id="VPSidebarNav">
    <div class="group"><section class="VPSidebarGroup">
      <div class="title"><h2 class="active title-text">开始</h2></div>
      <a class="link" href="/guide/introduction.html"><p class="link-text">简介</p></a>
      <a class="link" href="/guide/quick-start.html"><p class="link-text">快速上手</p></a>
    </section></div>
    <div class="group"><section class="VPSidebarGroup">
      <div class="title"><h2 class="title-text">深入组件</h2></div>
      <a class="link" href="/guide/components/registration.html"><p class="link-text">组件注册</p></a>
      <a class="link" href="/guide/components/props.html"><p class="link-text">Props</p></a>
      <a class="link" href="https://router.vuejs.org/zh/"><p class="link-text">Vue Router</p></a>
    </section></div>
  </nav>
</aside>
<main><h1>简介</h1><h2>什么是 Vue？</h2><p>Vue 是一款用于构建用户界面的 JavaScript 框架。</p></main>
</body></html>"""


def _doc_page(title: str, body: str) -> str:
    """生成一个无侧边栏的正文子页（模拟已渲染的文档内容页）。"""
    return (f"<html><head><title>{title} | Vue.js</title></head>"
            f"<body><main><h1>{title}</h1><p>{body}</p></main></body></html>")


# 结构化模式抓取映射：入口页（含侧边栏）+ 侧边栏声明的全部子页
STRUCTURED_PAGES = {
    BASE: SIDEBAR_HTML,
    "https://cn.vuejs.org/guide/quick-start.html":
        _doc_page("快速上手", "直接用 script 标签引入即可开始。"),
    "https://cn.vuejs.org/guide/components/registration.html":
        _doc_page("组件注册", "组件需要注册后才能被使用。"),
    "https://cn.vuejs.org/guide/components/props.html":
        _doc_page("Props", "子组件通过 props 接收数据。"),
}

# 无侧边栏入口页（应回落 BFS）
NO_SIDEBAR_HTML = ('<html><body><h1>索引</h1>'
                   '<a href="/docs/a.html">页面甲</a>'
                   '<a href="/docs/b.html">页面乙</a></body></html>')
FALLBACK_PAGES = {
    "https://docs.example.com/index.html": NO_SIDEBAR_HTML,
    "https://docs.example.com/docs/a.html": _doc_page("页面甲", "内容甲。"),
    "https://docs.example.com/docs/b.html": _doc_page("页面乙", "内容乙。"),
}


def _patch_fetch(monkeypatch: pytest.MonkeyPatch, pages: dict[str, str]) -> list[str]:
    """把 fetch.fetch_html 替换为离线映射；返回被请求 URL 的记录列表。"""
    calls: list[str] = []

    def fake_fetch_html(url: str, browser: dict | None = None) -> str:
        calls.append(url)
        if url not in pages:
            raise AssertionError(f"意外出网请求: {url}")
        return pages[url]

    monkeypatch.setattr(fetch, "fetch_html", fake_fetch_html)
    return calls


# ---------------------------------------------------------------------------
# 离线：侧边栏解析
# ---------------------------------------------------------------------------
def test_sidebar_parse_offline():
    items = sidebar_parser.parse_sidebar(SIDEBAR_HTML, BASE)
    assert items, "应至少解析出侧边栏条目"

    chapters = [i for i in items if i["level"] == 1]
    pages = [i for i in items if i["level"] == 2]
    # ≥2 个一级章节，且顺序与文档一致
    assert [c["title"] for c in chapters] == ["开始", "深入组件"]
    # 若干二级页：4 个同域页面 + 1 个跨域外链
    assert len(pages) == 5
    assert pages[0] == {"title": "简介",
                        "url": "https://cn.vuejs.org/guide/introduction.html",
                        "level": 2}
    assert pages[2]["url"] == "https://cn.vuejs.org/guide/components/registration.html"
    # 跨域外链保留为绝对地址
    assert pages[4] == {"title": "Vue Router",
                        "url": "https://router.vuejs.org/zh/", "level": 2}
    # 顶部导航（nav.menu）与正文 h2 不应混入
    assert "首页" not in [i["title"] for i in items]
    assert "什么是 Vue？" not in [c["title"] for c in chapters]


def test_sidebar_chapter_link_offline():
    """章节标题本身是链接时（VitePress 可折叠组），应输出带 url 的 level=1。"""
    html = ('<aside class="VPSidebar"><div class="group">'
            '<div class="title"><a class="title-link" href="/api/">API</a></div>'
            '<a class="link" href="/api/application.html"><p class="link-text">应用</p></a>'
            '</div></aside>')
    items = sidebar_parser.parse_sidebar(html, BASE)
    assert items[0] == {"title": "API", "url": "https://cn.vuejs.org/api/", "level": 1}
    assert items[1]["level"] == 2 and items[1]["title"] == "应用"


def test_sidebar_parse_empty_offline():
    """无侧边栏结构 / 纯顶部导航 / 空输入 → 返回 []（调用方回落 BFS）。"""
    assert sidebar_parser.parse_sidebar("<html><body><p>正文</p></body></html>", BASE) == []
    assert sidebar_parser.parse_sidebar(
        '<nav class="menu"><a href="/x.html">顶部</a></nav>', BASE) == []
    assert sidebar_parser.parse_sidebar("", BASE) == []


def test_group_by_top_level_offline():
    items = sidebar_parser.parse_sidebar(SIDEBAR_HTML, BASE)
    groups = sidebar_parser.group_by_top_level(items)
    assert list(groups) == ["开始", "深入组件"]
    assert [p["title"] for p in groups["开始"]] == ["简介", "快速上手"]
    assert [p["title"] for p in groups["深入组件"]] == ["组件注册", "Props", "Vue Router"]
    # 首个章节之前出现页面 → 归入未分组
    leading = sidebar_parser.group_by_top_level(
        [{"title": "首页", "url": "https://cn.vuejs.org/", "level": 2}] + items)
    assert leading["(未分组)"][0]["title"] == "首页"


# ---------------------------------------------------------------------------
# 离线：结构化整站爬取（目录树 + _index.json）
# ---------------------------------------------------------------------------
def test_site_structured_offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    calls = _patch_fetch(monkeypatch, STRUCTURED_PAGES)
    out_dir = tmp_path / "vue_site"

    result = site_crawl.crawl_site(BASE, output_dir=out_dir, max_pages=10,
                                   interval=0.0, structured=True)

    assert result["code"] == 0, result
    data = result["data"]
    assert data["mode"] == "structured"
    assert "fallback_bfs" not in data
    assert data["count"] == 4  # 3 个同域侧边栏页 + 入口页自身（外链不抓取）
    assert data["chapters"] == ["开始", "深入组件"]

    # 目录树：一级章节一个子目录（序号-slug），每页一个 md
    assert (out_dir / "01-开始" / "introduction.md").is_file()
    assert (out_dir / "01-开始" / "quick-start.md").is_file()
    assert (out_dir / "02-深入组件" / "registration.md").is_file()
    assert (out_dir / "02-深入组件" / "props.md").is_file()
    quick = (out_dir / "01-开始" / "quick-start.md").read_text(encoding="utf-8")
    assert "# 快速上手" in quick and "> 来源: " in quick

    # _index.json 结构：侧边栏全量结构 + 页面清单 + 失败清单
    index = json.loads((out_dir / "_index.json").read_text(encoding="utf-8"))
    assert index["mode"] == "structured" and index["entry_url"] == BASE
    assert set(index["sidebar"]) == {"开始", "深入组件"}
    assert [p["title"] for p in index["sidebar"]["开始"]] == ["简介", "快速上手"]
    assert len(index["pages"]) == 4
    assert index["pages"][0]["chapter"] == "开始"
    assert all(p["path"] for p in index["pages"])
    assert index["failed"] == []
    # 请求去重：入口页复用 HTML，总请求数 = 唯一同域页面数
    assert len(calls) == 4


def test_site_structured_max_pages_offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """max_pages 截断：只抓前 N 个侧边栏页，全部成功仍返回 code=0。"""
    _patch_fetch(monkeypatch, STRUCTURED_PAGES)
    result = site_crawl.crawl_site(BASE, output_dir=tmp_path / "cut",
                                   max_pages=2, interval=0.0, structured=True)
    assert result["code"] == 0
    assert result["data"]["count"] == 2


def test_site_fallback_bfs_offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """入口页无侧边栏 → 回落 BFS，data 注明 fallback_bfs=true。"""
    _patch_fetch(monkeypatch, FALLBACK_PAGES)
    out_dir = tmp_path / "bfs_site"

    result = site_crawl.crawl_site("https://docs.example.com/index.html",
                                   output_dir=out_dir, max_pages=10,
                                   interval=0.0, structured=True)

    assert result["code"] == 0, result
    data = result["data"]
    assert data["fallback_bfs"] is True and data["mode"] == "bfs"
    assert data["count"] == 3
    assert (out_dir / "docs_a.html.md").is_file()
    assert (out_dir / "docs_b.html.md").is_file()


def test_site_structured_blocked_offline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """入口页抓取异常（如反爬拦截）→ 诚实返回 3004，不伪装成功。"""
    def boom(url: str, browser: dict | None = None) -> str:
        raise RuntimeError("403 Forbidden")

    monkeypatch.setattr(fetch, "fetch_html", boom)
    result = site_crawl.crawl_site(BASE, output_dir=tmp_path / "blocked",
                                   max_pages=5, interval=0.0, structured=True)
    assert result["code"] == 3004
    assert result["data"]["failed"][0]["url"] == BASE


# ---------------------------------------------------------------------------
# 网络用例：默认跳过，ASTROFORGE_NETWORK_TEST=1 时真实请求 cn.vuejs.org
# ---------------------------------------------------------------------------
requires_network = pytest.mark.skipif(
    not os.environ.get("ASTROFORGE_NETWORK_TEST"),
    reason="设置 ASTROFORGE_NETWORK_TEST=1 才运行真站用例",
)


@requires_network
def test_sidebar_parse_real_vue():
    html = fetch.fetch_html("https://cn.vuejs.org/guide/introduction.html")
    items = sidebar_parser.parse_sidebar(
        html, "https://cn.vuejs.org/guide/introduction.html")
    chapters = [i["title"] for i in items if i["level"] == 1]
    pages = [i for i in items if i["level"] == 2]
    assert len(chapters) >= 2, f"一级章节过少: {chapters}"
    assert any(i["url"].startswith("https://cn.vuejs.org/") for i in pages)


@requires_network
def test_site_structured_real_vue(tmp_path: Path):
    result = site_crawl.crawl_site("https://cn.vuejs.org/guide/introduction.html",
                                   output_dir=tmp_path / "vue_real",
                                   max_pages=5, interval=0.5, structured=True)
    assert result["code"] == 0
    assert result["data"]["mode"] == "structured"
    assert (tmp_path / "vue_real" / "_index.json").is_file()
