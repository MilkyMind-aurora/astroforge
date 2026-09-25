# -*- coding: utf-8 -*-
# ============================================================
# AstroForge TUI 设计常量（生成物 —— scripts/gen_design.py，禁手改）
# 源：config/design/tokens.yaml + icons.yaml（sha256:80f421055903）
# 消费：壳层/页面一律引用语义名（design.DARK["aurora"]、design.icons.nav.home、
#       design.icon("nav.home")），禁散落硬编码色值与星符（§3.7 门禁 grep 断言）。
# ============================================================
from __future__ import annotations

from types import SimpleNamespace
from typing import Any

TOKENS_VERSION = 1
SOURCE_SHA256 = "80f421055903"
DEFAULT_THEME = "deep-space"
THEMES: tuple[str, ...] = ("dawn", "deep-space",)
THEME_MODE: dict[str, str] = {
    "dawn": "light",
    "deep-space": "dark",
}

# ---- 色板（root tokens 双档解析；键=语义名，值=#RRGGBB）----
LIGHT: dict[str, str] = {
    "bg": "#F6F7FC",
    "sunken": "#E8EBF4",
    "card": "#FFFFFF",
    "container": "#EDEFF7",
    "cardRaised": "#FFFFFF",
    "containerPressed": "#E2E5F0",
    "faint": "#E0E4F0",
    "ink-900": "#131629",
    "ink-600": "#565B76",
    "ink-400": "#606681",
    "stroke": "#C9CEE4",
    "strokeFocus": "#3A4066",
    "aurora": "#0C9B7E",
    "auroraText": "#087560",
    "nebula": "#6C5CE7",
    "nebulaText": "#5B4ED1",
    "hydrogen": "#1668B3",
    "molten": "#A66F14",
    "moltenText": "#8F5F0F",
    "nova": "#C3272B",
    "onAurora": "#131629",
    "onNebula": "#131629",
    "onHydrogen": "#F6F7FC",
    "onMolten": "#131629",
    "onNova": "#F6F7FC",
    "chipsSelectedBg": "#E2F3F0",
    "aiContainerBg": "#EAE8FC",
    "errorWashBg": "#F9E9EA",
    "runningWashBg": "#E2F3F0",
    "alertWashBg": "#E2F3F0",
}

DARK: dict[str, str] = {
    "bg": "#05070F",
    "sunken": "#0A0D18",
    "card": "#10131F",
    "container": "#171B2C",
    "cardRaised": "#171B2C",
    "containerPressed": "#1F2438",
    "faint": "#222741",
    "ink-900": "#EDF0FB",
    "ink-600": "#9AA1C0",
    "ink-400": "#858CB1",
    "stroke": "#2A2F4D",
    "strokeFocus": "#3A4066",
    "aurora": "#4EE0C0",
    "auroraText": "#4EE0C0",
    "nebula": "#8B7CF6",
    "nebulaText": "#8B7CF6",
    "hydrogen": "#4FC3F7",
    "molten": "#FFB74D",
    "moltenText": "#FFB74D",
    "nova": "#FF5648",
    "onAurora": "#05070F",
    "onNebula": "#05070F",
    "onHydrogen": "#05070F",
    "onMolten": "#05070F",
    "onNova": "#05070F",
    "chipsSelectedBg": "#172C32",
    "aiContainerBg": "#21223D",
    "errorWashBg": "#281A23",
    "runningWashBg": "#141F29",
    "alertWashBg": "#15232C",
}

# ---- 主题包解析值（点分键覆盖合并后按各主题 mode 取档；未覆盖键回落全局）----
THEME_PALETTE: dict[str, dict[str, str]] = {
    "dawn": {
            "bg": "#F6F7FC",
            "sunken": "#E8EBF4",
            "card": "#FFFFFF",
            "container": "#EDEFF7",
            "cardRaised": "#FFFFFF",
            "containerPressed": "#E2E5F0",
            "faint": "#E0E4F0",
            "ink-900": "#131629",
            "ink-600": "#565B76",
            "ink-400": "#606681",
            "stroke": "#C9CEE4",
            "strokeFocus": "#3A4066",
            "aurora": "#0C9B7E",
            "auroraText": "#087560",
            "nebula": "#6C5CE7",
            "nebulaText": "#5B4ED1",
            "hydrogen": "#1668B3",
            "molten": "#A66F14",
            "moltenText": "#8F5F0F",
            "nova": "#C3272B",
            "onAurora": "#131629",
            "onNebula": "#131629",
            "onHydrogen": "#F6F7FC",
            "onMolten": "#131629",
            "onNova": "#F6F7FC",
            "chipsSelectedBg": "#E2F3F0",
            "aiContainerBg": "#EAE8FC",
            "errorWashBg": "#F9E9EA",
            "runningWashBg": "#E2F3F0",
            "alertWashBg": "#E2F3F0",
    },
    "deep-space": {
            "bg": "#05070F",
            "sunken": "#0A0D18",
            "card": "#10131F",
            "container": "#171B2C",
            "cardRaised": "#171B2C",
            "containerPressed": "#1F2438",
            "faint": "#222741",
            "ink-900": "#EDF0FB",
            "ink-600": "#9AA1C0",
            "ink-400": "#858CB1",
            "stroke": "#2A2F4D",
            "strokeFocus": "#3A4066",
            "aurora": "#4EE0C0",
            "auroraText": "#4EE0C0",
            "nebula": "#8B7CF6",
            "nebulaText": "#8B7CF6",
            "hydrogen": "#4FC3F7",
            "molten": "#FFB74D",
            "moltenText": "#FFB74D",
            "nova": "#FF5648",
            "onAurora": "#05070F",
            "onNebula": "#05070F",
            "onHydrogen": "#05070F",
            "onMolten": "#05070F",
            "onNova": "#05070F",
            "chipsSelectedBg": "#172C32",
            "aiContainerBg": "#21223D",
            "errorWashBg": "#281A23",
            "runningWashBg": "#141F29",
            "alertWashBg": "#15232C",
    },
}

def css_variables(theme: str = DEFAULT_THEME) -> dict[str, str]:
    """Textual CSS 变量表：合并进 App.CSS_VARIABLES，refresh_css 瞬时切主题（§1.5）。"""
    try:
        return dict(THEME_PALETTE[theme])
    except KeyError:
        raise ValueError(f"未知主题: {theme}（可选: {', '.join(THEMES)}）") from None

GALAXY: dict[str, Any] = {
    "dark": ["#4EE0C0", "#8B7CF6", "#4FC3F7"],
    "light": ["#0C9B7E", "#6C5CE7", "#1668B3"],
    "positions": [0.0, 0.52, 1.0],
}

RADIUS: dict[str, Any] = {
        "pill": 999,
        "lg": 20,
        "md": 16,
        "sm": 12,
}

SPACE: dict[str, Any] = {
        "window": 20,
        "card": 16,
        "gap": 8,
        "gap-lg": 12,
        "section": 24,
        "section-lg": 32,
        "empty": 96,
}

TYPE: dict[str, Any] = {
        "display": {"size": 32, "height": 40, "weight": 600},
        "h1": {"size": 24, "height": 32, "weight": 600},
        "h2": {"size": 20, "height": 28, "weight": 500},
        "title": {"size": 17, "height": 24, "weight": 500},
        "title-sm": {"size": 15, "height": 22, "weight": 500},
        "body": {"size": 14, "height": 22, "weight": 400},
        "body-sm": {"size": 13, "height": 20, "weight": 400},
        "caption": {"size": 12, "height": 18, "weight": 400},
        "label": {"size": 11, "height": 16, "weight": 500},
        "kpi": {"size": 28, "height": 34, "weight": 500, "mono": True, "tabular": True},
}

STARFIELD: dict[str, Any] = {
        "alpha_steps": [0.04, 0.08, 0.12],
        "size_steps": [1.0, 1.5, 2.0],
        "density": [60, 90],
        "drift_dp": 2.0,
        "drift_period_s": 4.0,
        "meteor_interval_s": 120,
        "meteor_duration_ms": 250,
        "degrade_rule": "帧率 <45 持续 5s → uDensity=0；golden test 冻结 uTime=0",
}

MOTION_TUI: dict[str, Any] = {
        "t_press": {"duration_ms": 120, "easing": "in_out_cubic"},
        "t_slide": {"duration_ms": 250, "easing": "out_cubic"},
        "t_fade": {"duration_ms": 200, "easing": "in_out_sine"},
        "t_stream_batch": "2~4 token/帧合批（增量 append，禁整块重排）",
}

INTERACTION: dict[str, Any] = {
        "hit_min_dp": 40,
        "gesture": {
            "sheet_dismiss": {"distance_dp": 96, "velocity_dps": 1000, "rule": "位移或速度满足其一"},
            "drawer_open": {"distance_ratio": 0.4, "velocity_dps": 800},
            "long_press_ms": 400,
            "slop_dp": 8,
            "swipe_confirm_ratio": 0.8,
        },
        "keyboard": {"nav_debounce_ms": 30, "palette_debounce_ms": 150},
        "states": [
            "default",
            "hover",
            "pressed",
            "selected",
            "disabled",
            "loading",
            "success",
            "error",
            "empty",
            "readonly",
        ],
}

MONO_FAMILY = "JetBrainsMono"

# tui.border_levels 三档解析值（subtle/normal/active → hex）
BORDER_LEVELS: dict[str, str] = {
    "subtle": "#222741",
    "normal": "#2A2F4D",
    "active": "#4EE0C0",
}
THINKING_OPACITY = 0.6

# ---- 星符表（icons.yaml；引用一律走语义名：icons.nav.home / icon("status.ok")）----
ICONS: dict[str, str] = {
    "nav.home": "✦",
    "nav.spider": "☄",
    "nav.parser": "◈",
    "nav.converter": "❖",
    "nav.pipeline": "✺",
    "nav.monitor": "◉",
    "nav.history": "☾",
    "nav.settings": "✜",
    "nav.task": "✧",
    "ai.idle": "✵",
    "ai.thinking": "✶",
    "ai.thinking_f2": "✷",
    "ai.thinking_f3": "✸",
    "ai.done": "☄",
    "ai.send": "✵",
    "ai.fallback": "✧",
    "status.ok": "●",
    "status.idle": "◌",
    "status.error": "✕",
    "status.warn": "▲",
    "status.hint": "✧",
    "task.running": "◈",
    "task.running_f2": "◉",
    "task.pending": "○",
    "task.success": "✓",
    "task.failed": "✕",
    "task.canceled": "⊘",
    "misc.meteor": "☄",
    "misc.star_rank_1": "✦",
    "misc.star_rank_2": "✦✦",
    "misc.star_rank_3": "✧",
    "misc.binary_star": "✦✧",
    "misc.spinner_f1": "◐",
    "misc.spinner_f2": "◓",
    "misc.spinner_f3": "◑",
    "misc.spinner_f4": "◒",
    "misc.star_dim": "·",
    "misc.star_mid": "•",
}

def icon(path: str) -> str:  # 例：icon("ai.thinking_f2")
    """按语义名取星符；未知名直接报错（宁可炸也不给错字）。"""
    try:
        return ICONS[path]
    except KeyError:
        raise ValueError(f"未知星符: {path}（可选: {len(ICONS)} 个语义名）") from None


def _ns(tree: dict[str, Any]) -> Any:
    """扁平点分键 → 嵌套 SimpleNamespace（icons.nav.home 属性访问）。"""
    return SimpleNamespace(
        **{k: (_ns(v) if isinstance(v, dict) else v) for k, v in tree.items()}
    )


def _icon_tree() -> dict[str, Any]:
    tree: dict[str, Any] = {}
    for path, glyph in ICONS.items():
        parts = path.split(".")
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = glyph
    return tree


icons: SimpleNamespace = _ns(_icon_tree())
