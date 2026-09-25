# -*- coding: utf-8 -*-
"""TUI 页面插件机制（方案 §2.4 / V1-B.3，MF2）。

三层插件模型的 L2：页面 = PagePlugin 协议对象。
- 内置 8 页随包分发（tui/plugins/<key>/，同 key 内置优先）；
- 第三方页经 entry_points 组 astroforge.tui_pages 注入（pip 装进
  env_astroforge 即挂入 UI，不动主干）；入口对象须为 PagePlugin 或其
  asdict dict，坏插件逐个跳过不拖垮壳层；
- config/design/pages.yaml（L1 数据插件）做显隐/排序覆盖：visible=false
  的页面从侧边栏与命令面板同时隐藏，order 覆盖插件 sort；整文件缺失=
  全部可见、按插件 sort 排。
插件页环境依赖缺失时由壳层把侧栏健康点降级为「缺失/异常」（与首页体检
同源 env-check，方案 §2.4 降级纪律）。
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from importlib.metadata import entry_points
from pathlib import Path
from typing import Any, Callable

import yaml

ENTRY_POINT_GROUP = "astroforge.tui_pages"
PAGES_YAML = Path(__file__).resolve().parents[3] / "config" / "design" / "pages.yaml"
_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class PagePlugin:
    """页面插件契约（方案 §2.4）：key/title/icon/sort/factory + 可选 env_dep。"""

    key: str
    title: str
    icon: str                       # icons.yaml 语义名（禁裸星符，§3.7 门禁④）
    sort: int
    factory: Callable[..., Any]     # (client, app_ref) -> Widget
    env_dep: tuple[str, ...] = ()   # env-check 项名子串（健康点同源；空=聚合全部）

    def __post_init__(self) -> None:
        if not _KEY_RE.match(self.key):
            raise ValueError(f"插件 key 非法: {self.key!r}（须为小写标识符）")
        from tui.theme.generated import tokens as design

        if self.icon not in design.ICONS:
            raise ValueError(f"插件 {self.key} 星符语义名未注册: {self.icon}")


def from_mapping(payload: dict[str, Any]) -> PagePlugin:
    """dict → PagePlugin（第三方入口的宽松装载面）。"""
    return PagePlugin(**payload)


def to_mapping(plugin: PagePlugin) -> dict[str, Any]:
    return asdict(plugin)


def builtin_plugins() -> list[PagePlugin]:
    """内置 8 页（导入即注册；顺序无关，collect 统一排序）。"""
    from tui.plugins.converter import plugin as converter
    from tui.plugins.history import plugin as history
    from tui.plugins.home import plugin as home
    from tui.plugins.monitor import plugin as monitor
    from tui.plugins.parser import plugin as parser
    from tui.plugins.pipeline import plugin as pipeline
    from tui.plugins.settings import plugin as settings
    from tui.plugins.spider import plugin as spider

    return [home, spider, parser, converter, pipeline, monitor, history, settings]


def entry_point_plugins(group: str = ENTRY_POINT_GROUP) -> list[PagePlugin]:
    """扫描 entry_points（pip 装进 env_astroforge 的第三方页）；坏插件逐个跳过。"""
    plugins: list[PagePlugin] = []
    try:
        eps = entry_points(group=group)
    except Exception:
        return plugins
    for ep in eps:
        try:
            loaded = ep.load()
        except Exception:
            continue  # 入口指向的包坏了不拖垮壳层
        try:
            plugins.append(loaded if isinstance(loaded, PagePlugin)
                           else from_mapping(dict(loaded)))
        except Exception:
            continue
    return plugins


def load_pages_overrides(path: Path = PAGES_YAML) -> dict[str, dict[str, Any]]:
    """读 pages.yaml 覆盖层；缺文件/坏文件=空覆盖（全部可见，按 sort）。"""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    pages = data.get("pages")
    return {str(k): dict(v or {}) for k, v in pages.items()} if isinstance(pages, dict) else {}


def collect_plugins(overrides: dict[str, dict[str, Any]] | None = None) -> list[PagePlugin]:
    """内置 + entry_points 合并（同 key 内置优先）→ pages.yaml 显隐/排序覆盖。"""
    if overrides is None:
        overrides = load_pages_overrides()
    merged: dict[str, PagePlugin] = {}
    for plugin in (*builtin_plugins(), *entry_point_plugins()):
        merged.setdefault(plugin.key, plugin)
    visible: list[PagePlugin] = [
        plugin for key, plugin in merged.items()
        if overrides.get(key, {}).get("visible") is not False
    ]
    visible.sort(key=lambda p: (int(overrides.get(p.key, {}).get("order", p.sort)), p.sort))
    return visible
