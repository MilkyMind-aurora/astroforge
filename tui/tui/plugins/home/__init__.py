# -*- coding: utf-8 -*-
"""首页插件（方案 §2.4 L2）：key=home，无独立模块环境依赖。"""
from __future__ import annotations

from tui.plugins import PagePlugin
from tui.plugins.home.page import HomePage

plugin = PagePlugin(
    key="home", title="首页", icon="nav.home", sort=1, env_dep=(),
    factory=lambda client, app_ref: HomePage(client, app_ref),
)

__all__ = ["HomePage", "plugin"]
