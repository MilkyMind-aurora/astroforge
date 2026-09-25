# -*- coding: utf-8 -*-
"""流水线插件（方案 §2.4 L2）：key=pipeline，env_dep=Conda（NovaFlow 依赖模块环境）。"""
from __future__ import annotations

from tui.plugins import PagePlugin
from tui.plugins.pipeline.page import PipelinePage

plugin = PagePlugin(
    key="pipeline", title="流水线", icon="nav.pipeline", sort=5, env_dep=("Conda",),
    factory=lambda client, app_ref: PipelinePage(client, app_ref),
)

__all__ = ["PipelinePage", "plugin"]
