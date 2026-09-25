# -*- coding: utf-8 -*-
"""采集中心插件（方案 §2.4 L2）：key=spider，env_dep=Chromium（爬取依赖浏览器）。"""
from __future__ import annotations

from tui.plugins import PagePlugin
from tui.plugins.spider.page import SpiderPage

plugin = PagePlugin(
    key="spider", title="采集中心", icon="nav.spider", sort=2, env_dep=("Chromium",),
    factory=lambda client, app_ref: SpiderPage(client, app_ref),
)

__all__ = ["SpiderPage", "plugin"]
