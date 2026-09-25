# -*- coding: utf-8 -*-
"""首页 hero 星点框（方案 §3.2 / §1.5）：seed.json 预生成坐标 → 静态 3 行星野。

终端不做循环动画（性能红线，§3.7 反面清单）；星点字符/亮度档取自
icons.yaml 生成物（misc.star_dim/star_mid/star_rank_1），禁散落硬编码星符。
"""
from __future__ import annotations

import json
from pathlib import Path

from tui.theme.generated import tokens as design

_SEED_PATH = Path(__file__).resolve().parents[3] / "config" / "design" / "starfield" / "seed.json"

# 亮度档 → 星符语义名（seed tier0 暗星多、tier2 亮星少）
_TIER_ICON = ("misc.star_dim", "misc.star_mid", "misc.star_rank_1")


def load_stars(path: Path = _SEED_PATH) -> list[dict]:
    """读星野种子；缺文件返回空（首页降级为无星框，不阻断）。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return list(data.get("stars", []))
    except (OSError, json.JSONDecodeError):
        return []


def render_starfield(width: int, rows: int = 3, stars: list[dict] | None = None) -> str:
    """确定性渲染星点框：把归一化坐标映射进 rows×width 字符画（纯静态）。

    同一 seed + 同一尺寸必得同一画面（无随机源），符合「预生成禁每帧随机」。
    """
    if width <= 0 or rows <= 0:
        return ""
    grid: list[list[str]] = [[" "] * width for _ in range(rows)]
    pool = stars if stars is not None else load_stars()
    # 亮星优先落格：按 tier 降序绘制，同格冲突时暗星不覆盖亮星
    for star in sorted(pool, key=lambda s: -int(s["tier"])):
        col = int(star["x"] * width)
        row = min(rows - 1, int(star["y"] * rows))
        if 0 <= col < width and grid[row][col] == " ":
            grid[row][col] = design.icon(_TIER_ICON[star["tier"]])
    return "\n".join("".join(line).rstrip() for line in grid)
