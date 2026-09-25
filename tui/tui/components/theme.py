# -*- coding: utf-8 -*-
"""RichLog 等滚动缓冲组件的主题取色助手（panels 与插件详情抽屉共用）。

RichLog 滚动缓冲是已渲染的 Strip 序列，不随主题热切重渲；其行样式取「写入时
的当前主题」token hex（生成物 THEME_PALETTE 常量，禁裸色，§3.7 门禁①）。
Static 等常规组件仍用 `[$aurora]` 变量 markup（可随主题热切）。
"""
from __future__ import annotations

from rich.text import Text

from tui.theme.generated import tokens as design


def theme_token(app, token: str) -> str:
    """当前主题下的 token hex（生成物 THEME_PALETTE；未知主题回落默认档）。"""
    name = app.theme if app.theme in design.THEMES else design.DEFAULT_THEME
    return design.THEME_PALETTE[name][token]


def rich_line(app, parts: list[tuple[str, str | None]]) -> Text:
    """分段样式行（RichLog 内容不解析 Textual $变量 markup，逐段 Text.append）。"""
    text = Text()
    for content, token in parts:
        text.append(content, style=theme_token(app, token) if token else None)
    return text
