# -*- coding: utf-8 -*-
"""CLI 星幕渲染器（方案 §2.5 / §四）。

顶部「星空设计 token」段由 scripts/gen_design.py 生成（禁手改）；渲染器四件套
（banner/stage/progress/result_card/error_card/log）于 V1-B.4/MF3 落地，届时
颜色与星符一律取自生成段（运行时也可直读 config/design/tokens.yaml）。
降级纪律【硬性】：非 TTY 或 rich 不可导入 → 全部回退纯文本；stdout 日志行
（``[INFO] ``/``[ERROR] `` 前缀）与结果 JSON 契约字节不变（服务核心逐行捕获零改动）。
"""
from __future__ import annotations

# ==== BEGIN 星空设计 token（scripts/gen_design.py 生成，禁手改）====
# 源：config/design/tokens.yaml + icons.yaml（sha256:80f421055903）
# 消费：CLI 全部颜色/星符一律取自本段（裸色/裸星符=违反设计契约）；
#       富文本色用 STAR_TOKENS，纯文本降级路径不取色（字节契约不变）。
STAR_TOKENS: dict[str, dict[str, str]] = {
    "dark": {
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
    "light": {
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
}
STAR_GALAXY: dict[str, list[str]] = {
    "dark": ["#4EE0C0", "#8B7CF6", "#4FC3F7"],
    "light": ["#0C9B7E", "#6C5CE7", "#1668B3"],
}
STAR_ICONS: dict[str, str] = {
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
# ==== END 星空设计 token ====

def palette(mode: str = "dark") -> dict[str, str]:
    """指定档 token 表（MF3 渲染器与降级路径共用的取色入口；值一律来自生成段）。"""
    try:
        return dict(STAR_TOKENS[mode])
    except KeyError:
        raise ValueError(f"未知色彩档: {mode}（可选: dark/light）") from None
