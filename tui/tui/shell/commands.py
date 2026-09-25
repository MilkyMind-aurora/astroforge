# -*- coding: utf-8 -*-
"""命令面板（方案 §3.6，插件注册表驱动）：/ 唤起，输入防抖 150ms（Provider 自带）。

命令全集：注册页直达 / 文件浏览器 / 日志面板 / 星伴 / 主题切换（deep-space/dawn）
/ 刷新体检 / 重连。页面项随插件注册表与 pages.yaml 显隐动态生成（§2.4）。
"""
from __future__ import annotations

from textual.command import DiscoveryHit, Hits, Provider

from tui.theme.generated import tokens as design


class ForgeCommands(Provider):

    def _commands(self) -> list[tuple[str, object]]:
        app = self.app
        items: list[tuple[str, object]] = [
            (f"{design.icon(plugin.icon)} {index + 1} {plugin.title}",
             lambda idx=index: app.switch_page(idx))
            for index, plugin in enumerate(app.pages)
        ]
        items += [
            ("打开文件浏览器", app.action_file_browser),
            ("打开日志面板", app.action_toggle_log),
            ("星伴 AI", app.action_ai_panel),
            ("刷新体检", app.action_refresh_env),
            *[(
                f"主题：{name}（{'夜 · 默认' if name == design.DEFAULT_THEME else '昼'}）",
                lambda name=name: app.action_set_theme(name),
            ) for name in design.THEMES],
            ("重连服务核心", app.reconnect),
        ]
        return items

    async def discover(self) -> Hits:
        for title, callback in self._commands():
            yield DiscoveryHit(title, callback)

    async def search(self, query: str) -> Hits:
        for title, callback in self._commands():
            if query.lower() in title.lower():
                yield DiscoveryHit(title, callback)
