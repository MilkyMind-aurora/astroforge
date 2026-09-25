# -*- coding: utf-8 -*-
"""星仔吉祥物（Phase 8.3 帧 + MF2 台词库外置，规格见 design/星仔生命感与彩蛋系统规格v1.md）。

ASCII 帧保留（V1 帧；星球化 V2 形态属 Flutter 自绘引擎，TUI 红线禁循环动画，
帧轮换仅可见位运行）；台词库迁出至 config/design/quotes.yaml（L1 数据插件，
唯一事实源）——本模块保留 QUOTES 兼容映射与 get_quote() 抽样入口：
uniform + no_repeat_window 3 + 深夜改投（0-5 点 boot/idle_long 40% → midnight）。
调度上限（cooldown/每日 cap）属 MascotDirector 语义，TUI 仅 boot 单触发位，
不在此伪造限额执行。
"""
from __future__ import annotations

import random
from collections import deque
from pathlib import Path

import yaml

FRAMES = {
    "idle": r"""
    *  _____  *
     /       \
    |  o   o  |
    |    ‿    |
     \  ___  /_>
      |::::|
       """
    ,
    "idle_blink": r"""
    *  _____  *
     /       \
    |  -   o  |
    |    ‿    |
     \  ___  /_>
      |::::|
       """,
    "happy": r"""
  \   _____   /
   * /       \ *
    |  ^   ^  |
    |    ◡    |
     \ \___/ /
      |::::|/
   ~~~~~~~~~~~~~
   """,
    "error": r"""
   ~  ~   ~
    *  _____  *
     /  x  x  \
    |    ▽    |
     \  ___  /
      |::::|
       """,
    "sleeping": r"""
    *  _____  *
     /  ‿   ‿  \
    |    ‿     |
     \  ___  /
      |::::|  z
             z
   """,
}

# 台词库唯一事实源（星仔规格 §二；gen_design 校验单条 ≤24 字）
QUOTES_PATH = Path(__file__).resolve().parents[3] / "config" / "design" / "quotes.yaml"

# 旧事件名 → quotes.yaml 事件组（兼容既有调用点：get_quote("boot"/"success"/…）)
_EVENT_ALIASES = {
    "boot": "boot",
    "first_task": "first_task",
    "idle": "idle_long",
    "success": "task_success",
    "error": "task_fail",
    "fallback": "ai_fallback",
    "late_night": "midnight",
    "task_success": "task_success",
    "task_fail": "task_fail",
    "pipeline_complete": "pipeline_complete",
    "idle_long": "idle_long",
    "reconnect": "reconnect",
    "meteor": "meteor",
    "midnight": "midnight",
    "memory_clear": "memory_clear",
    "ai_fallback": "ai_fallback",
}

_NO_REPEAT_WINDOW = 3   # quotes.yaml sampling.no_repeat_window
_MIDNIGHT_HOUR = (0, 5)  # 0-5 点改投区间
_MIDNIGHT_PROBABILITY = 0.4

_recent: dict[str, deque[str]] = {}
_fallback_line = "星仔在，炉火不熄。"


def load_quotes(path: Path = QUOTES_PATH) -> dict[str, list[str]]:
    """读台词库 {事件组: [台词]}；缺文件返回空表（调用方回落 _fallback_line）。"""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    events = data.get("events") or {}
    return {
        str(event): [str(line) for line in (group or {}).get("lines", [])]
        for event, group in events.items()
    }


def _pick(group: str, pool: list[str]) -> str:
    """uniform + no_repeat_window 3（组内最近 3 条不重复）。"""
    if not pool:
        return _fallback_line
    recent = _recent.setdefault(group, deque(maxlen=_NO_REPEAT_WINDOW))
    candidates = [line for line in pool if line not in recent] or pool
    return random.choice(candidates)


def get_quote(event: str, now_hour: int | None = None, pool: dict[str, list[str]]
              | None = None) -> str:
    """按事件取一条台词；深夜（0-5 点）boot/idle_long 按概率改投 midnight 池。

    纯函数入口（now_hour/pool 可注入，单测覆盖不依赖时钟与文件）。
    """
    quotes = pool if pool is not None else load_quotes()
    group = _EVENT_ALIASES.get(event, event)
    if now_hour is None:
        import datetime
        now_hour = datetime.datetime.now().hour
    if group in ("boot", "idle_long") and _MIDNIGHT_HOUR[0] <= now_hour < _MIDNIGHT_HOUR[1]:
        if random.random() < _MIDNIGHT_PROBABILITY and quotes.get("midnight"):
            return _pick("midnight", quotes["midnight"])
    return _pick(group, quotes.get(group, quotes.get("idle_long", [])))


def get_frame(name: str) -> str:
    return FRAMES.get(name, FRAMES["idle"])


# 兼容层：旧代码 `from tui.ui.mascot import QUOTES` 直读内存表（设置页预览等）
QUOTES: dict[str, list[str]] = load_quotes()
