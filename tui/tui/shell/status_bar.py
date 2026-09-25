# -*- coding: utf-8 -*-
"""底部状态栏（方案 §3.1，1 行全宽）：WS /ws/monitor 1s 驱动、500ms 刷新节流。

●已连接（aurora）/ ◌重连中（nova，仅断连时 1Hz 闪烁——状态反馈而非背景动画）；
内存 used/totalGB（>warn 熔金 / >crit nova）；任务运行数；AI；时刻；版本代号。
<80 列裁剪中间段仅留连接态与时间。
"""
from __future__ import annotations

from datetime import datetime

from textual.widgets import Static

from tui.plugins.monitor.page import mem_severity
from tui.shell.format import seg
from tui.theme.generated import tokens as design

VERSION_FALLBACK = "Sidereal Core v0.1.0"


class StatusBar(Static):

    def on_mount(self) -> None:
        self._last_line = ""
        self._blink = False
        self.set_interval(0.5, self._tick)

    def _tick(self) -> None:
        app = self.app
        state = app.monitor_state
        sample = state.get("sample")
        narrow = app.size.width < 80
        segments: list[str] = []
        # 连接态
        if state.get("ws_connected"):
            segments.append(seg(f"{design.icon('status.ok')} 已连接", "aurora"))
        else:
            self._blink = not self._blink
            mark = design.icon("status.idle") if self._blink else " "
            segments.append(seg(f"{mark} 重连中 · 数据冻结", "nova"))
        if not narrow:
            # 内存（阈值：config-summary monitor 段，缺省 10/12GB）
            if sample:
                used = float(sample.get("mem_used_gb", 0.0))
                percent = float(sample.get("mem_percent", 0.0))
                total = used / (percent / 100) if percent > 0 else 0.0
                color = mem_severity(used, state["warn_gb"], state["crit_gb"])
                total_txt = f"{total:.0f}" if total > 0 else "?"
                segments.append(
                    f"内存 {seg(f'{used:.1f}/{total_txt}GB', color)}")
            else:
                segments.append("[dim]内存 --[/dim]")
            running = int(state.get("running_count", 0))
            if running:
                segments.append(
                    f"任务 {running} 运行 {seg(design.icon('task.running'), 'aurora')}")
            else:
                segments.append(f"[dim]任务 0 待命 {design.icon('task.pending')}[/dim]")
            segments.append(
                seg(f"AI {design.icon('ai.idle')}", "nebula"))
        segments.append(datetime.now().strftime("%H:%M"))
        if not narrow:
            version = str((app.health_data or {}).get("version", "")) or VERSION_FALLBACK
            segments.append(f"[dim]v{version}[/dim]")
            segments.append("[dim]/ 命令 · q 退出[/dim]")
        line = " · ".join(segments)
        if line != self._last_line:  # 内容不变不重绘（节流纪律）
            self._last_line = line
            self.update(line)
