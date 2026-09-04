# -*- coding: utf-8 -*-
"""星仔吉祥物（Phase 8.3，设计规范见 docs/design/mascot.md）。

grok bot 造型语言的原创实现：blob 星星 + 锻造元素，纯 ASCII 帧保证
终端兼容；台词库按触发事件分组，mascot_enabled 开关由设置页控制。
"""
from __future__ import annotations

import random

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

QUOTES: dict[str, list[str]] = {
    "boot": [
        "熔炉点火完毕，今天也把混沌锻造成秩序。",
        "Sidereal Core 上线——恒星已进入主序带。",
        "星仔报到，数据氢准备好聚变了吗？",
    ],
    "idle": [
        "嘘……猎户座那边比我这边还安静。",
        "闲置也是蓄能，恒星不闪光的时候在攒核聚变。",
        "要不要喂我一点 PDF？",
    ],
    "success": [
        "锻造完成！这批数据已经烧掉三层杂质。",
        "交付 ✦ 星表上又多了一颗干净文档。",
        "核聚变结束，输出比输入亮多了。",
    ],
    "error": [
        "呃……有颗氢原子没听话。看看日志里谁在捣乱。",
        "熔炉打个嗝而已，重试一下就好。",
        "引力坍缩失败了，建议检查参数引力场。",
    ],
    "fallback": [
        "AI 走神了，已用快捷模式执行，建议检查参数。",
        "我打了个盹，靠肌肉记忆帮你跑完了——参数最好亲自看一眼。",
    ],
    "late_night": [
        "银河系此刻也很忙，但它没有暂停键。少熬夜，程序员。",
        "凌晨的终端和望远镜一样，都能看见别人看不见的东西。",
    ],
}


def get_quote(event: str) -> str:
    """按事件随机取一条台词；fallback 事件优先于深夜判断。"""
    import datetime

    if event == "boot" and datetime.datetime.now().hour >= 22:
        return random.choice(QUOTES["late_night"])
    return random.choice(QUOTES.get(event, QUOTES["idle"]))


def get_frame(name: str) -> str:
    return FRAMES.get(name, FRAMES["idle"])
