# -*- coding: utf-8 -*-
"""转换中心插件（方案 §2.4 L2）：key=converter，env_dep=anydoc+DOCX 模板。"""
from __future__ import annotations

from tui.plugins import PagePlugin
from tui.plugins.converter.page import ConverterPage

plugin = PagePlugin(
    key="converter", title="转换中心", icon="nav.converter", sort=4,
    env_dep=("anydoc", "DOCX 模板"),
    factory=lambda client, app_ref: ConverterPage(client, app_ref),
)

__all__ = ["ConverterPage", "plugin"]
