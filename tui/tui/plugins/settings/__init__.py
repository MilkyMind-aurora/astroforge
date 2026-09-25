# -*- coding: utf-8 -*-
"""设置页插件（方案 §2.4 L2）：key=settings，env_dep=PostgreSQL（app_settings）。"""
from __future__ import annotations

from tui.plugins import PagePlugin
from tui.plugins.settings.page import SettingsPage, quote_preview

plugin = PagePlugin(
    key="settings", title="设置", icon="nav.settings", sort=8,
    env_dep=("PostgreSQL",),
    factory=lambda client, app_ref: SettingsPage(client, app_ref),
)

__all__ = ["SettingsPage", "plugin", "quote_preview"]
