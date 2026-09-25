# -*- coding: utf-8 -*-
"""解析中心插件（方案 §2.4 L2）：key=parser，env_dep=MinerU。"""
from __future__ import annotations

from tui.plugins import PagePlugin
from tui.plugins.parser.page import ParserPage

plugin = PagePlugin(
    key="parser", title="解析中心", icon="nav.parser", sort=3, env_dep=("MinerU",),
    factory=lambda client, app_ref: ParserPage(client, app_ref),
)

__all__ = ["ParserPage", "plugin"]
