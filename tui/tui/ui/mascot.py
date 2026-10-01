# -*- coding: utf-8 -*-
"""星仔吉祥物（Phase 8.3 帧 + MF2 台词库外置，规格见 design/星仔生命感与彩蛋系统规格v1.md）。

ASCII 帧保留（V1 帧；星球化 V2 形态属 Flutter 自绘引擎，TUI 红线禁循环动画，
帧轮换仅可见位运行）；台词库迁出至 config/design/quotes.yaml（L1 数据插件，
唯一事实源）——本模块保留 QUOTES 兼容映射与 get_quote() 抽样入口：
uniform + no_repeat_window 3 + 深夜改投（0-5 点 boot/idle_long 40% → midnight）。
dispatch 段语义（M3）：cap_session / cap_lifetime_once / cooldown_s 由
QuoteDirector 在会话内执行；cap_day / trigger_idle_min 属跨会话调度，TUI 无
持久层不伪造（留 Flutter MascotDirector 落地）。
"""
from __future__ import annotations

import datetime
import random
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

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


def resolve_group(event: str, quotes: dict[str, list[str]], now_hour: int) -> str:
    """事件 → 实际台词组（quotes.yaml sampling.midnight_override：0-5 点概率改投）。

    纯决策（不抽样），QuoteDirector 依赖它先定组再判定 dispatch 限额。
    """
    group = _EVENT_ALIASES.get(event, event)
    if group in ("boot", "idle_long") and _MIDNIGHT_HOUR[0] <= now_hour < _MIDNIGHT_HOUR[1]:
        if random.random() < _MIDNIGHT_PROBABILITY and quotes.get("midnight"):
            return "midnight"
    return group


def _sample(group: str, quotes: dict[str, list[str]]) -> str:
    """组内抽样（缺组回落 idle_long 池；全空回落固定文案）。"""
    return _pick(group, quotes.get(group, quotes.get("idle_long", [])))


def get_quote(event: str, now_hour: int | None = None, pool: dict[str, list[str]]
              | None = None) -> str:
    """按事件取一条台词；深夜（0-5 点）boot/idle_long 按概率改投 midnight 池。

    纯函数入口（now_hour/pool 可注入，单测覆盖不依赖时钟与文件）；
    dispatch 限额判定见 QuoteDirector（本函数不带账）。
    """
    quotes = pool if pool is not None else load_quotes()
    if now_hour is None:
        now_hour = datetime.datetime.now().hour
    group = resolve_group(event, quotes, now_hour)
    return _sample(group, quotes)


# ============================================================
# dispatch 段执行（M3：quotes.yaml dispatch → cap_session/cap_lifetime_once/cooldown_s）
# ============================================================

@dataclass(frozen=True)
class DispatchRule:
    """dispatch 单组限额（与 quotes.yaml dispatch 段字段一一对应）。"""

    cap_session: int | None = None       # 会话内最多播报次数
    cap_lifetime_once: bool = False      # 进程生命周期一次（跨会话持久化属 MascotDirector）
    cooldown_s: float = 0.0              # 组内两次播报最小间隔秒


def load_dispatch(path: Path = QUOTES_PATH) -> dict[str, DispatchRule]:
    """读 dispatch 段 → {组: DispatchRule}；缺文件/坏文件返回空表（全放行）。"""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}
    rules: dict[str, DispatchRule] = {}
    for name, spec in (data.get("dispatch") or {}).items():
        spec = spec or {}
        rules[str(name)] = DispatchRule(
            cap_session=spec.get("cap_session"),
            cap_lifetime_once=bool(spec.get("cap_lifetime_once")),
            cooldown_s=float(spec.get("cooldown_s") or 0),
        )
    return rules


class QuoteDirector:
    """dispatch 语义执行器：announce() = 准入判定（allow）→ 抽样 → 记账。

    拒绝（超 cap/冷却中/生命周期已播）返回 None 且不消耗限额；放行即记账。
    clock 可注入（单测不依赖真实时钟）。
    """

    def __init__(self, rules: dict[str, DispatchRule] | None = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._rules = dict(rules) if rules is not None else load_dispatch()
        self._clock = clock
        self._session: dict[str, int] = {}
        self._fired_once: set[str] = set()
        self._last_at: dict[str, float] = {}

    def allow(self, group: str, now: float | None = None) -> bool:
        """dispatch 单组准入（只判定不记账；记账在 announce 落地时）。"""
        rule = self._rules.get(group, DispatchRule())
        if now is None:
            now = self._clock()
        if rule.cap_lifetime_once and group in self._fired_once:
            return False
        if rule.cap_session is not None and self._session.get(group, 0) >= rule.cap_session:
            return False
        last = self._last_at.get(group)
        if rule.cooldown_s > 0 and last is not None and now - last < rule.cooldown_s:
            return False
        return True

    def announce(self, event: str, now: float | None = None,
                 now_hour: int | None = None,
                 pool: dict[str, list[str]] | None = None) -> str | None:
        """请求播报一条台词：dispatch 拒绝 → None；放行 → 抽样并记账返回台词。

        深夜改投在定组阶段完成：改投 midnight 记 midnight 组的账（cap_session:1）。
        """
        quotes = pool if pool is not None else load_quotes()
        if not quotes:
            return None
        if now is None:
            now = self._clock()
        if now_hour is None:
            now_hour = datetime.datetime.now().hour
        group = resolve_group(event, quotes, now_hour)
        if not self.allow(group, now):
            return None
        rule = self._rules.get(group, DispatchRule())
        line = _sample(group, quotes)
        self._session[group] = self._session.get(group, 0) + 1
        if rule.cap_lifetime_once:
            self._fired_once.add(group)
        self._last_at[group] = now
        return line


def get_frame(name: str) -> str:
    return FRAMES.get(name, FRAMES["idle"])


# 兼容层：旧代码 `from tui.ui.mascot import QUOTES` 直读内存表（设置页预览等）
QUOTES: dict[str, list[str]] = load_quotes()
