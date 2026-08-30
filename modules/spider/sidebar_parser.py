# -*- coding: utf-8 -*-
"""文档站侧边栏导航解析（Phase 2 Task 2.1.3，方案 3.2「整站文档结构化爬取」）。

仅用标准库 html.parser，零第三方依赖。通用启发式（对 VitePress 系文档站
——如 cn.vuejs.org——实测有效，对常见 doc 站具备泛化性）：

1. 侧边栏容器定位（预扫描定优先级，避免顶部导航抢注）：
   a. class 含 "sidebar" 的元素（如 <aside class="VPSidebar">）；
   b. 否则第一个 <aside>；
   c. 否则第一个 <nav>（class 命中 navbar/menu/header/footer/outline/toc
      等顶部导航特征时排除）。
   三者都找不到 → 返回 []，由调用方回落 BFS。
2. 一级章节（level=1）：容器内「标题元素」的可见文本。标题元素 = h2-h6/
   summary/dt 标签，或 class 含 title/heading/caption 的 p/div/span/li/
   section；章节若是链接（标题元素内含 <a>）则带 url。
3. 页面条目（level=2）：容器内其余 <a href> + 可见文本作标题；链接经
   urljoin 转绝对地址并去掉 #fragment。
4. group 容器（class 含 group/section 等）不单独输出——分组交给
   group_by_top_level 按文档扫描顺序（章节标题出现即开新组）完成。
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from urllib.parse import urldefrag, urljoin, urlparse

# 未归入任何一级章节的页面落到此组（parse 顺序在首个章节标题之前）
UNGROUPED_KEY = "(未分组)"

# 预扫描：判断页面里是否存在「class 含 sidebar」的元素（带单/双引号两种写法）
_CLASS_SIDEBAR_RE = re.compile(r'class\s*=\s*["\'][^"\']*sidebar', re.IGNORECASE)
_ASIDE_RE = re.compile(r"<aside[\s>]", re.IGNORECASE)
_NAV_RE = re.compile(r"<nav[\s>]", re.IGNORECASE)
# 顶部导航特征类名：命中则不把该 <nav> 当侧边栏容器
_NAV_EXCLUDE_RE = re.compile(
    r"navbar|menu|header|footer|outline|toc|breadcrumb|pagination|tabs?", re.IGNORECASE
)
# 章节标题特征：class 含这些词
_TITLE_CLASS_RE = re.compile(r"title|heading|caption", re.IGNORECASE)
# 按「标签即标题」认定的标签（无需 class）
_TITLE_TAGS = frozenset({"h2", "h3", "h4", "h5", "h6", "summary", "dt"})
# 按「标签 + class」认定标题的标签集合
_TITLE_CLASS_TAGS = frozenset({"p", "div", "span", "li", "section"})
# 不收集文本的标签（避免 svg 图标 / 脚本混入标题与链接文本）
_SKIP_TAGS = frozenset({"script", "style", "svg", "template", "noscript"})
# 自闭合 void 元素：不参与开闭栈配对
_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input",
     "link", "meta", "param", "source", "track", "wbr"}
)
# 允许保留为页面/章节条目的协议
_ALLOWED_SCHEMES = {"http", "https"}


def _attr(attrs: list[tuple[str, str | None]], name: str) -> str:
    """取第一个同名属性值（缺失/为 None 返回空串）。"""
    for key, value in attrs:
        if key == name and value is not None:
            return value
    return ""


def _normalize_text(raw: str) -> str:
    """折叠空白并去首尾（VitePress 节点间常夹注释与换行）。"""
    return re.sub(r"\s+", " ", raw).strip()


def _container_rule(html: str) -> str | None:
    """预扫描确定容器定位规则（优先级：sidebar 类名 > aside > nav）。"""
    if _CLASS_SIDEBAR_RE.search(html):
        return "class"
    if _ASIDE_RE.search(html):
        return "aside"
    if _NAV_RE.search(html):
        return "nav"
    return None


class _SidebarParser(HTMLParser):
    """单遍流式解析：先锁定容器，再在容器内收集章节标题与页面链接。"""

    def __init__(self, rule: str, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.rule = rule
        self.base_url = base_url
        self.items: list[dict] = []
        # 开标签栈：tag 与 class 平行，用于容器/标题闭合判定
        self.stack: list[str] = []
        self.stack_classes: list[str] = []
        self.container_depth: int | None = None
        self.skip_depth = 0
        # 当前捕获中的章节标题（title_depth = 标题元素入栈后的栈深）
        self.title_depth: int | None = None
        self.title_buf: list[str] = []
        self.title_url = ""
        # 当前捕获中的链接（link_depth = <a> 入栈后的栈深）
        self.link_depth: int | None = None
        self.link_buf: list[str] = []
        self.link_href = ""
        self.link_is_title = False

    # ---- 判定辅助 -------------------------------------------------------
    def _matches_container(self, tag: str, classes: str) -> bool:
        if self.rule == "class":
            return "sidebar" in classes.lower()
        if self.rule == "aside":
            return tag == "aside"
        # rule == "nav"
        return tag == "nav" and not _NAV_EXCLUDE_RE.search(classes)

    def _is_title_element(self, tag: str, classes: str) -> bool:
        if tag in _TITLE_TAGS:
            return True
        return tag in _TITLE_CLASS_TAGS and bool(_TITLE_CLASS_RE.search(classes))

    def _abs_url(self, href: str) -> str | None:
        """相对链接转绝对地址并去 #fragment；非 http(s) 返回 None。"""
        href = (href or "").strip()
        if not href or href.startswith("#"):
            return None
        absolute = urldefrag(urljoin(self.base_url, href))[0]
        if urlparse(absolute).scheme not in _ALLOWED_SCHEMES:
            return None
        return absolute

    def _emit_chapter(self, title: str, url: str) -> None:
        """输出一级章节；与上一条同名章节合并，避免重复开组。"""
        if self.items:
            last = self.items[-1]
            if last["level"] == 1 and last["title"] == title:
                if url and not last["url"]:
                    last["url"] = url
                return
        self.items.append({"title": title, "url": url, "level": 1})

    # ---- 标题 / 链接捕获 -------------------------------------------------
    def _on_anchor_start(self, href: str, classes: str) -> None:
        if self.link_depth is not None:
            return  # 嵌套 <a>（非法 HTML），忽略内层
        self.link_depth = len(self.stack)
        self.link_buf = []
        self.link_href = href
        # a 自身带 title/heading 类 → 该链接即章节链接
        self.link_is_title = bool(_TITLE_CLASS_RE.search(classes))

    def _on_anchor_end(self) -> None:
        text = _normalize_text("".join(self.link_buf))
        href, is_title = self.link_href, self.link_is_title
        self.link_depth, self.link_buf = None, []
        self.link_href, self.link_is_title = "", False
        if self.title_depth is not None:
            # 标题内链接：归并进章节（补 url），不作为页面条目
            if text and not self.title_url:
                self.title_url = self._abs_url(href) or ""
            return
        if not text:
            return
        url = self._abs_url(href)
        if url is None:
            return
        self.items.append(
            {"title": text, "url": url, "level": 1 if is_title else 2}
        )

    def _emit_pending_chapter(self) -> None:
        text = _normalize_text("".join(self.title_buf))
        url = self.title_url
        self.title_depth, self.title_buf, self.title_url = None, [], ""
        if text:
            self._emit_chapter(text, url)

    # ---- HTMLParser 事件 -------------------------------------------------
    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[name-defined]
        classes = _attr(attrs, "class")
        href = _attr(attrs, "href")
        is_void = tag in _VOID_TAGS

        if self.container_depth is None:
            if self._matches_container(tag, classes):
                self.container_depth = len(self.stack) + 1
            if not is_void:
                self.stack.append(tag)
                self.stack_classes.append(classes)
            return

        if not is_void:
            self.stack.append(tag)
            self.stack_classes.append(classes)

        if tag in _SKIP_TAGS:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag == "a":
            if href is not None:
                self._on_anchor_start(href, classes)
            return
        if self.link_depth is not None:
            return  # 链接内部普通标签：仅待文本收集
        if self.title_depth is None and self.link_depth is None and self._is_title_element(tag, classes):
            self.title_depth = len(self.stack)
            self.title_buf = []
            self.title_url = ""

    def handle_endtag(self, tag: str) -> None:
        if self.container_depth is None:
            return
        if tag in _VOID_TAGS or tag not in self.stack:
            return  # 游离闭合标签：忽略（栈配对容错）
        while self.stack:
            popped = self.stack.pop()
            self.stack_classes.pop()
            if popped == tag:
                break
        if tag in _SKIP_TAGS and self.skip_depth:
            self.skip_depth -= 1
        # 链接闭合：弹出后栈深低于其入栈深度即为本 <a> 的闭合
        if self.link_depth is not None and len(self.stack) < self.link_depth:
            self._on_anchor_end()
        # 章节标题闭合
        if self.title_depth is not None and len(self.stack) < self.title_depth:
            self._emit_pending_chapter()
        # 侧边栏容器闭合：此后不再收集（多容器页面只认第一个）
        if len(self.stack) < self.container_depth:
            self.container_depth = None

    def handle_data(self, data: str) -> None:
        if self.skip_depth or self.container_depth is None:
            return
        if self.link_depth is not None:
            self.link_buf.append(data)
        if self.title_depth is not None:
            self.title_buf.append(data)


def parse_sidebar(html: str, base_url: str) -> list[dict]:
    """从文档站 HTML 解析侧边栏导航。

    返回有序列表 [{"title": 章节名, "url": 绝对链接, "level": 1|2}, ...]；
    解析不到容器或任何条目时返回 []（调用方回落 BFS）。
    """
    if not html or not isinstance(html, str):
        return []
    rule = _container_rule(html)
    if rule is None:
        return []
    parser = _SidebarParser(rule, base_url)
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # 解析异常按「无侧边栏」处理，由调用方回落
        return []
    return parser.items


def group_by_top_level(items: list[dict]) -> dict[str, list[dict]]:
    """按一级章节分组：level==1 的条目作为组键，其后 level==2 依序归组。

    - 章节自身带链接时，作为该组第一个条目保留（level=1）；
    - 组内按 url 去重（章节链接与首个页面重合等情形）；
    - 出现在首个章节之前的页面归入 UNGROUPED_KEY。
    """
    grouped: dict[str, list[dict]] = {}
    current: str | None = None
    for item in items:
        level = item.get("level")
        url = item.get("url") or ""
        if level == 1:
            current = item.get("title") or UNGROUPED_KEY
            bucket = grouped.setdefault(current, [])
            if url and all(entry.get("url") != url for entry in bucket):
                bucket.append({"title": item.get("title") or current,
                               "url": url, "level": 1})
        else:
            bucket = grouped.setdefault(current or UNGROUPED_KEY, [])
            if url and all(entry.get("url") != url for entry in bucket):
                bucket.append(dict(item))
    return grouped
