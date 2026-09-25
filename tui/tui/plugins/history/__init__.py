# -*- coding: utf-8 -*-
"""任务历史插件（方案 §2.4 L2）：key=history，env_dep=PostgreSQL（任务库）。"""
from __future__ import annotations

from tui.plugins import PagePlugin
from tui.plugins.history.page import HistoryDetailScreen, HistoryPage

plugin = PagePlugin(
    key="history", title="任务历史", icon="nav.history", sort=7,
    env_dep=("PostgreSQL",),
    factory=lambda client, app_ref: HistoryPage(client, app_ref),
)

__all__ = ["HistoryDetailScreen", "HistoryPage", "plugin"]
