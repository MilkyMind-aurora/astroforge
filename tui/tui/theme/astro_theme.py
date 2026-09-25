# -*- coding: utf-8 -*-
"""把设计契约生成物（tokens.py）装配为 Textual 主题（方案 §1.5 / V1.2-1）。

- tokens.css_variables(theme) 提供语义变量（$aurora / $ink-900 / $chipsSelectedBg…），
  App.CSS 与各屏 CSS 一律按语义名引用；hex 字面量只允许出现在 generated/ 生成物
  （§3.7 门禁①，ui_doctor bare-color 断言）。
- 同时映射 Textual 内建色系统（$primary/$surface/$panel/$text…），让 Button/Input/
  DataTable/OptionList 等内建组件零改动吃进星空色板。
- 主题热切 = `app.theme = <name>`（Textual 原生刷新变量并 refresh_css，瞬时生效）。
"""
from __future__ import annotations

from textual.theme import Theme

from tui.theme.generated import tokens as design

# 语义变量 → Textual 内建色系统映射（aurora=全局唯一主强调，§1.1）
_COLOR_SYSTEM_MAP = {
    "primary": "aurora",
    "secondary": "nebula",      # AI 专属位
    "warning": "molten",
    "error": "nova",
    "success": "aurora",
    "accent": "hydrogen",
    "foreground": "ink-900",
    "background": "bg",
    "surface": "card",
    "panel": "container",
    "boost": "containerPressed",
}


def build_theme(name: str) -> Theme:
    """tokens 语义变量 → Textual Theme（内建色系统映射 + 语义变量注入）。"""
    palette = design.css_variables(name)
    variables: dict[str, str] = dict(palette)
    # 盒式语言边框三档（V1.2-1：subtle/normal/active）+ AI 思考块透明度
    variables.update({
        "border-subtle": design.BORDER_LEVELS["subtle"],
        "border-normal": design.BORDER_LEVELS["normal"],
        "border-active": design.BORDER_LEVELS["active"],
        "thinking-opacity": str(design.THINKING_OPACITY),
    })
    system = {role: palette[token] for role, token in _COLOR_SYSTEM_MAP.items()}
    return Theme(
        name=name,
        dark=design.THEME_MODE.get(name) == "dark",
        variables=variables,
        **system,
    )


#: 全部内置主题（tokens.THEMES：deep-space 默认夜 + dawn 昼），注册进 App 用
ASTRO_THEMES: dict[str, Theme] = {name: build_theme(name) for name in design.THEMES}
DEFAULT_THEME = design.DEFAULT_THEME
