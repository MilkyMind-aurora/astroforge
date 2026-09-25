# -*- coding: utf-8 -*-
"""壳层渲染助手：状态栏色段 / 跑圈帧 / nova 错误行（token 变量，禁裸色）。"""
from __future__ import annotations

from tui.theme.generated import tokens as design


def seg(text: str, color: str) -> str:
    """状态栏色段（$语义变量；[/] 自动闭合）。"""
    return f"[${color}]{text}[/]"


def spinner_frame(frame: int) -> str:
    """跑圈字符（icons.yaml misc.spinner_f1..f4，#17 边缘高亮跑圈）。"""
    return design.icon(f"misc.spinner_f{frame % 4 + 1}")


def error_mark(head: str, detail: str) -> str:
    """nova 色错误行（统一页面错误文案格式）。"""
    return f"{seg(design.icon('status.error') + ' ' + head, 'nova')} {detail}"
