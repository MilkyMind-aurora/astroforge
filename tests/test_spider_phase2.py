# -*- coding: utf-8 -*-
"""正文结构化提取 + 断点续爬离线测试（Phase 2 收尾）。"""
import json

from site_crawl import _load_state, _save_state, crawl_site

PAGE1_HTML = """
<html><head><title>测试站</title></head><body>
<h1>总览</h1>
<p>这是 <a href="/doc/page2.html">第二页</a> 的入口。</p>
<ul><li>要点一</li><li>要点二</li></ul>
<pre><code>print("hello")</code></pre>
<blockquote>引用内容</blockquote>
<script>console.log("skip me")</script>
</body></html>
"""

PAGE2_HTML = """
<html><head><title>第二页</title></head><body>
<h2>细节</h2><p>第二页正文。</p>
</body></html>
"""


def test_markdown_structured_output():
    from fetch import html_to_md

    text, title = html_to_md(PAGE1_HTML, base_url="https://example.com/doc/page1.html")
    assert title == "测试站"
    assert text.startswith("# 总览")                     # 标题层级
    assert "[第二页](https://example.com/doc/page2.html)" in text  # 链接绝对化
    assert "- 要点一" in text and "- 要点二" in text      # 无序列表
    assert "```" in text and 'print("hello")' in text    # 代码块
    assert "> 引用内容" in text                          # 引用块
    assert "skip me" not in text                         # script 被跳过


def test_relative_link_uses_base_url():
    from fetch import html_to_md

    text, _ = html_to_md('<a href="sub/x.html">x</a>', base_url="https://s.io/a/")
    assert "https://s.io/a/sub/x.html" in text


def test_crawl_state_roundtrip(tmp_path):
    _save_state(tmp_path, {"https://a/1", "https://a/2"}, {"https://a/3": "timeout"})
    state = _load_state(tmp_path)
    assert set(state["completed"]) == {"https://a/1", "https://a/2"}
    assert state["failed"] == {"https://a/3": "timeout"}


def test_bfs_resume_skips_completed(tmp_path, monkeypatch):
    """断点续爬：已完成页面不再发起请求（入口页除外）。"""
    import fetch

    calls: list[str] = []

    def fake_fetch_html(url: str, browser: dict | None = None) -> str:
        calls.append(url)
        return PAGE1_HTML if "page1" in url else PAGE2_HTML

    monkeypatch.setattr(fetch, "fetch_html", fake_fetch_html)
    out = tmp_path / "site"

    first = crawl_site("https://example.com/doc/page1.html", out, max_pages=5, interval=0)
    assert first["code"] == 0 and first["data"]["count"] >= 2
    assert len(calls) == 2

    # 重跑：page2 已完成，不应再请求它（入口页仍会抓取）
    calls.clear()
    monkeypatch.setattr(
        fetch, "fetch_html",
        lambda url, browser=None: (calls.append(url), PAGE1_HTML)[1],
    )
    second = crawl_site("https://example.com/doc/page1.html", out, max_pages=5, interval=0)
    assert second["code"] == 0
    assert all("page2" not in u for u in calls), f"断点续爬失效，仍请求了已完成页面: {calls}"
    state = _load_state(out)
    assert "https://example.com/doc/page2.html" in state["completed"]


def test_structured_index_written(tmp_path, monkeypatch):
    """结构化模式写 _index.json 且 data 带章节信息。"""
    import fetch

    sidebar_html = (
        '<html><head><title>入口</title></head><body><aside>'
        '<nav><div class="group"><h3>开始</h3>'
        '<a href="https://example.com/guide/intro.html">简介</a>'
        '<a href="https://example.com/guide/quick.html">快速上手</a>'
        "</div></nav></aside></body></html>"
    )
    pages = {
        "https://example.com/guide/intro.html": PAGE2_HTML,
        "https://example.com/guide/quick.html": PAGE2_HTML,
    }

    def fake_fetch_html(url: str, browser: dict | None = None) -> str:
        return sidebar_html if url.endswith("entry.html") else pages.get(url, PAGE2_HTML)

    monkeypatch.setattr(fetch, "fetch_html", fake_fetch_html)
    result = crawl_site(
        "https://example.com/guide/entry.html", tmp_path / "s",
        max_pages=5, interval=0, structured=True, resume=False,
    )
    assert result["code"] == 0
    assert result["data"]["mode"] == "structured"
    index = json.loads((tmp_path / "s" / "_index.json").read_text(encoding="utf-8"))
    assert "开始" in index["sidebar"]
    # 入口页不在侧边栏清单时补抓为第 3 页（设计行为）
    assert len(index["pages"]) == 3
