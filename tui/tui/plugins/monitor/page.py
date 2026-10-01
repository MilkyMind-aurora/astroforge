# -*- coding: utf-8 -*-
"""监控看板 · 星象台（方案 §3.4，插件页：tui/plugins/monitor/，MF1 落地 MF2 迁入）。

- KPI 行：CPU % / 内存 GB / 磁盘 MB/s / 运行任务数（等宽数字，1s WS 驱动，
  页面刷新节流 500ms）
- Sparkline 曲线：Textual Sparkline，窗口 60 点（CPU=极光青 / 内存=氢蓝）
- 进程表：本机 AstroForge 相关进程（PID/名称/环境/CPU/内存），运行行前置
  ◈/◉ 1s 有界交替帧（task.running/running_f2，set_interval 仅运行期间起表，
  L15）
- 告警区：内存阈值（>10GB 熔金 / >12GB nova，阈值取自 config-summary）+
  WS type=alert 实时事件（信封 {type:alert,payload:{level,source,message,
  task_uuid?}}，L16；服务端广播由 server 组实现）；有未处理告警时 aurora-wash
  底。规格 v1 §1.8 的 wash 呼吸在终端不落地——§3.7 红线「禁连续背景动画」，
  TUI 取静态 wash（取舍如实注明，L15）。
- 历史回放：range 胶囊（统一 ChipBar，L17）实时|1h|6h|24h（GET /monitor/history，
  整段重绘）
- 告警行 Enter：按 task_uuid 定位任务详情（无 uuid 回落切历史页，L16）

数据契约：/ws/monitor（app 层 1s 采集入 MonitorState + alert 事件入队）+
/api/v1/monitor/history。进程表为本机 psutil 直采（服务核心无进程清单 API，
TUI 与服务同机运行）。
"""
from __future__ import annotations

import re
import time
from collections import deque
from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import (
    DataTable,
    OptionList,
    Sparkline,
    Static,
)
from textual.widgets.option_list import Option

from tui.components.chips import ChipBar
from tui.components.env_gate import GATE_INTERVAL_S, EnvGateMixin
from tui.theme.generated import tokens as design

WINDOW_POINTS = 60          # Sparkline 滚动窗口（方案 §3.4）
POLL_INTERVAL = 0.5         # KPI/曲线刷新节流 500ms
PROC_INTERVAL = 5.0         # 进程表扫描周期
RUN_FRAME_INTERVAL_S = 1.0  # 运行行 ◈/◉ 交替帧周期（L15，仅运行期间起表）
REPO_ROOT = Path(__file__).resolve().parents[4]

# 模块 cli.py 路径段 → conda 环境名（进程表「环境」列推断；task_scheduler.MODULE_MAP 同源）
_MODULE_ENVS = {
    "spider": "env_spider", "mineru": "env_mineru", "wpd": "env_wpd",
    "anydoc": "env_anydoc", "md2docx": "env_md2docx",
}

RUN_ICONS = ("task.running", "task.running_f2")  # ◈/◉ 交替帧（icons.yaml 帧动画）


def mem_severity(mem_gb: float, warn_gb: float, crit_gb: float) -> str:
    """内存档位 → 颜色 token 名（>crit=nova / >warn=molten / 正常=ink-900）。"""
    if mem_gb > crit_gb:
        return "nova"
    if mem_gb > warn_gb:
        return "molten"
    return "ink-900"


def format_kpi_row(
    sample: dict, running: int, warn_gb: float, crit_gb: float,
    read_mbps: float = 0.0, write_mbps: float = 0.0,
) -> str:
    """KPI 行渲染（等宽数字；内存值随阈值变色）。"""
    mem_gb = float(sample.get("mem_used_gb", 0.0))
    color = mem_severity(mem_gb, warn_gb, crit_gb)
    return (
        f"[b]CPU[/b] {float(sample.get('cpu_percent', 0.0)):5.1f}%    "
        f"[b]内存[/b] [${color}]{mem_gb:5.1f}GB[/${color}]    "
        f"[b]磁盘[/b] R{read_mbps:5.1f}/W{write_mbps:5.1f}MB/s    "
        f"[b]任务[/b] {design.icon('task.running')} {running} 运行"
    )


def derive_alerts(
    sample: dict | None, warn_gb: float, crit_gb: float, ws_connected: bool,
) -> list[tuple[str, str]]:
    """本地告警推导 → [(级别 token, 文案)]；warn=熔金 ▲ / error=nova ✕。

    服务端 WS alert 事件（L16）由 _render_alerts 与本推导并入同列。
    """
    alerts: list[tuple[str, str]] = []
    if sample is not None:
        mem_gb = float(sample.get("mem_used_gb", 0.0))
        if mem_gb > crit_gb:
            alerts.append(("error", f"内存 {mem_gb:.1f}GB 超红线 {crit_gb:g}GB，建议收任务"))
        elif mem_gb > warn_gb:
            alerts.append(("warn", f"内存 {mem_gb:.1f}GB 超预警 {warn_gb:g}GB"))
    if not ws_connected:
        alerts.append(("warn", "监控通道 /ws/monitor 断开，等待重连（数据已冻结）"))
    return alerts


def infer_env(cmdline: list[str]) -> str:
    """从命令行推断 conda 环境：modules/<m>/cli.py > env_<name> 显式命中 > 服务核心 > -。"""
    joined = " ".join(cmdline).lower().replace("\\", "/")
    for module, env in _MODULE_ENVS.items():
        if f"modules/{module}/" in joined:
            return env
    match = re.search(r"env_([a-z0-9_]+)/", joined)
    if match:
        return f"env_{match.group(1)}"
    if "astroforge" in joined:
        return "env_astroforge"
    return "-"


def _display_name(cmdline: list[str], fallback: str) -> str:
    """进程显示名：modules/<m>/cli.py → 模块名；否则取首个非解释器参数/回退名。"""
    for token in cmdline:
        low = token.lower().replace("\\", "/")
        if "/modules/" in low and low.endswith(".py"):
            return low.rsplit("/modules/", 1)[-1].replace("/", " · ")
    for token in cmdline[2:]:
        if token.startswith("-"):
            continue
        return Path(token).name[:20]
    return fallback[:20]


def scan_processes(repo_root: Path = REPO_ROOT, limit: int = 20) -> list[dict]:
    """本机 AstroForge 相关进程（命令行含仓库路径）；按内存降序取前 limit 行。

    CPU% 依赖 psutil 两次采样（interval=None 首次恒 0），5s 周期下第二帧起为真值。
    """
    try:
        import psutil
    except ImportError:
        return []
    root_key = str(repo_root).lower().replace("\\", "/")
    rows: list[dict] = []
    for proc in psutil.process_iter(["pid", "name", "cmdline", "memory_info"]):
        try:
            info = proc.info
            cmdline = list(info.get("cmdline") or [])
            hay = " ".join(cmdline).lower().replace("\\", "/")
            if not cmdline or root_key not in hay:
                continue
            mem_info = info.get("memory_info")
            rows.append({
                "pid": info["pid"],
                "name": _display_name(cmdline, info.get("name") or "?"),
                "env": infer_env(cmdline),
                "cpu": proc.cpu_percent(interval=None),
                "mem_mb": round(mem_info.rss / 1024 / 1024, 1) if mem_info else 0.0,
                "module_task": any(
                    t.lower().endswith("cli.py") and "modules" in t.lower() for t in cmdline
                ),
            })
        except Exception:  # psutil.NoSuchProcess/AccessDenied 等逐进程容错
            continue
    rows.sort(key=lambda row: -row["mem_mb"])
    return rows[:limit]


class MonitorPage(VerticalScroll, EnvGateMixin):
    """星象台：KPI + 曲线 + 进程表 + 告警 + 历史回放。"""

    GATE_DISABLE = ("#mon-range",)  # PG 缺失：历史回放入口禁用（实时区不受影响）

    def __init__(self, client, app_ref=None) -> None:  # noqa: ANN001（App 循环依赖）
        super().__init__(id="page-monitor")
        self.client = client
        self._app = app_ref
        self._range = "实时"
        self._alert_signature = ""
        self._alert_targets: dict[str, str | None] = {}  # 行 id → task_uuid（L16）
        self._proc_rows: list[dict] = []                 # 最近一次进程扫描缓存
        self._run_frame = 0                              # ◈/◉ 交替帧计数
        self._run_timer = None                           # 交替帧表（仅运行期间起）

    def compose(self) -> ComposeResult:
        yield Static(
            f"[b]{design.icon('nav.monitor')} 监控看板 · 星象台[/b]"
            f"  [dim]NovaFlow 资源曲线 / 进程 / 告警 / 历史回放[/dim]",
            id="mon-title", classes="page-body",
        )
        yield Static("等待 /ws/monitor 首帧…", id="mon-kpis")
        with Horizontal(id="mon-sparks"):
            yield Sparkline(
                [], summary_function=max, name="CPU%",
                min_color=design.DARK["aurora"], max_color=design.DARK["aurora"], id="spark-cpu",
            )
            yield Sparkline(
                [], summary_function=max, name="内存GB",
                min_color=design.DARK["hydrogen"], max_color=design.DARK["hydrogen"],
                id="spark-mem",
            )
        yield ChipBar(  # L17：range 统一胶囊 chips（去 RadioSet）
            [("实时", "实时"), ("1h", "1h"), ("6h", "6h"), ("24h", "24h")],
            id="mon-range",
        )
        yield Static("[b]告警[/b]", id="mon-alerts-title")
        yield OptionList(id="mon-alerts", classes="alerted-off")
        yield DataTable(id="mon-procs")

    def on_mount(self) -> None:
        table = self.query_one("#mon-procs", DataTable)
        table.add_columns("PID", "名称", "环境", "CPU%", "内存MB")
        table.cursor_type = "row"
        self.set_interval(POLL_INTERVAL, self._tick)
        self.set_interval(PROC_INTERVAL, self._tick_procs)
        self.set_interval(GATE_INTERVAL_S, self.apply_env_gate)  # L9② 环境门禁
        self.call_later(self.apply_env_gate)  # 首查（异步门禁）
        self._tick_procs()

    # ---- 实时区（app.MonitorState → UI） ----
    def _tick(self) -> None:
        if self._range != "实时":
            return
        app = self._app
        if app is None:
            return
        state = app.monitor_state
        sample = state["sample"]
        if sample is None:
            return
        self.query_one("#mon-kpis", Static).update(format_kpi_row(
            sample, state["running_count"], state["warn_gb"], state["crit_gb"],
            state["read_mbps"], state["write_mbps"],
        ))
        cpu = self.query_one("#spark-cpu")
        mem = self.query_one("#spark-mem")
        cpu.data = list(state["cpu_window"])
        mem.data = list(state["mem_window"])
        # L16：本地推导 + WS type=alert 实时事件并入一列
        self._render_alerts(
            derive_alerts(sample, state["warn_gb"], state["crit_gb"],
                          state["ws_connected"]),
            list(state.get("ws_alerts") or []),
        )

    def _render_alerts(self, alerts: list[tuple[str, str]],
                       ws_alerts: list[dict] | None = None) -> None:
        """告警渲染（L16）：本地推导 + WS alert 并列；带 task_uuid 的行记入
        _alert_targets，Enter 按 uuid 定位任务详情。"""
        entries: list[tuple[str, str, str | None]] = [
            (level, text, None) for level, text in alerts]
        for item in ws_alerts or []:
            message = str(item.get("message") or "").strip()
            if not message:
                continue
            level = "error" if str(item.get("level")) == "error" else "warn"
            source = str(item.get("source") or "server")
            uuid = str(item.get("task_uuid") or "") or None
            entries.append((level, f"[{source}] {message}", uuid))
        signature = "|".join(f"{level}:{text}:{uuid}" for level, text, uuid in entries)
        if signature == self._alert_signature:
            return
        self._alert_signature = signature
        self._alert_targets = {f"alert-{index}": uuid
                               for index, (_l, _t, uuid) in enumerate(entries)}
        board = self.query_one("#mon-alerts", OptionList)
        board.clear_options()
        if not entries:
            board.add_option(Option(
                f"[$aurora]{design.icon('status.ok')}[/$aurora] 星域平静 · 无告警",
                id="alert-none",
            ))
            board.remove_class("alerted")
            self.query_one("#mon-alerts-title", Static).update("[b]告警[/b]")
            return
        board.add_class("alerted")
        self.query_one("#mon-alerts-title", Static).update(
            f"[b]告警[/b]  [$molten]{len(entries)} 条待处理[/$molten]"
            if all(level == "warn" for level, _t, _u in entries) else
            f"[b]告警[/b]  [$nova]{len(entries)} 条待处理[/$nova]"
        )
        for index, (level, text, _uuid) in enumerate(entries):
            if level == "error":
                mark = f"[$nova]{design.icon('status.error')}[/$nova]"
            else:
                mark = f"[$molten]{design.icon('status.warn')}[/$molten]"
            board.add_option(Option(f" {mark} {text}", id=f"alert-{index}"))

    # ---- 进程表（◈/◉ 1s 有界交替帧，仅运行期间起表，L15）----
    def _tick_procs(self) -> None:
        self._proc_rows = scan_processes()
        self._render_procs()
        has_running = any(row["module_task"] for row in self._proc_rows)
        if has_running and self._run_timer is None:
            self._run_timer = self.set_interval(RUN_FRAME_INTERVAL_S, self._tick_run_frame)
        elif not has_running and self._run_timer is not None:
            self._run_timer.stop()
            self._run_timer = None

    def _tick_run_frame(self) -> None:
        self._run_frame += 1
        self._render_procs()

    def _render_procs(self) -> None:
        table = self.query_one("#mon-procs", DataTable)
        table.clear(columns=False)
        icon = design.icon(RUN_ICONS[self._run_frame % len(RUN_ICONS)])
        for row in self._proc_rows:
            prefix = (f"[dim]{icon}[/dim] " if row["module_task"] else "  ")
            table.add_row(
                str(row["pid"]), f"{prefix}{row['name']}", row["env"],
                f"{row['cpu']:.1f}", f"{row['mem_mb']:.0f}",
            )

    # ---- 历史回放（range 胶囊 → /monitor/history 整段重绘） ----
    def on_chip_bar_changed(self, event: ChipBar.Changed) -> None:
        if event.chip_bar.id != "mon-range":
            return
        label = str(event.value)
        self._range = label
        if label == "实时":
            return
        self.run_worker(self._load_history(label), exclusive=True)

    async def _load_history(self, label: str) -> None:
        kpis = self.query_one("#mon-kpis", Static)
        kpis.update(f"[dim]回放 {label}：拉取 /monitor/history…[/dim]")
        try:
            data = await self.client.monitor_history(label)
        except Exception as exc:
            kpis.update(f"[$nova]历史拉取失败[/$nova]  {exc}")
            return
        points = list((data or {}).get("points", []))
        if not points:
            kpis.update(f"[dim]回放 {label}：暂无聚合点（服务运行满 10s 后开始累积）[/dim]")
        else:
            cpu_avg = sum(p["cpu_percent"] for p in points) / len(points)
            mem_avg = sum(p["mem_used_gb"] for p in points) / len(points)
            kpis.update(
                f"[dim]回放 {label} · {len(points)} 点 · "
                f"CPU 均值 {cpu_avg:.1f}% · 内存均值 {mem_avg:.1f}GB[/dim]"
            )
        self.query_one("#spark-cpu").data = [p["cpu_percent"] for p in points]
        self.query_one("#spark-mem").data = [p["mem_used_gb"] for p in points]

    # ---- 告警行 Enter → 按 task_uuid 定位任务详情（L16）----
    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option_id or ""
        if self._app is None or not option_id.startswith("alert-"):
            return
        if option_id == "alert-none":
            return
        task_uuid = self._alert_targets.get(option_id)
        if not task_uuid:
            self._app.switch_page_by_key("history")  # 无 uuid 回落：仅切历史页
            return
        self.run_worker(self._open_task_detail(task_uuid), exclusive=True)

    async def _open_task_detail(self, task_uuid: str) -> None:
        from tui.plugins.history.page import HistoryDetailScreen  # 局部导入防环

        try:
            detail = await self.client.task_detail(task_uuid)
        except Exception as exc:
            self.app.notify(f"任务详情拉取失败：{exc}", severity="error")
            return
        self._app.switch_page_by_key("history")  # 底页先切历史（关抽屉即落在任务处）
        self._app.push_screen(HistoryDetailScreen(self.client, detail))


class MonitorState(dict):
    """监控通道共享状态（app 层 WS worker 写入，状态栏与看板共读）。

    以 dict 子类承载便于直接下标读取；字段：
    sample/prev_ts/read_mbps/write_mbps/cpu_window/mem_window/ws_connected/
    running_count/warn_gb/crit_gb/updated_at/ws_alerts（L16：type=alert 事件队列）
    """

    @classmethod
    def create(cls, warn_gb: float, crit_gb: float) -> MonitorState:
        return cls({
            "sample": None, "prev_ts": 0.0, "read_mbps": 0.0, "write_mbps": 0.0,
            "cpu_window": deque(maxlen=WINDOW_POINTS),
            "mem_window": deque(maxlen=WINDOW_POINTS),
            "ws_connected": False, "running_count": 0,
            "warn_gb": warn_gb, "crit_gb": crit_gb, "updated_at": 0.0,
            "ws_alerts": deque(maxlen=20),
        })

    def ingest(self, sample: dict) -> None:
        """并入一帧 /ws/monitor 采样：滚动窗口 + 磁盘速率差分。"""
        now = time.monotonic()
        prev = self["sample"]
        if prev is not None and now > self["prev_ts"] > 0.0:
            dt = now - self["prev_ts"]
            self["read_mbps"] = max(
                0.0, (float(sample.get("disk_read_mbps", 0.0))
                      - float(prev.get("disk_read_mbps", 0.0))) / dt)
            self["write_mbps"] = max(
                0.0, (float(sample.get("disk_write_mbps", 0.0))
                      - float(prev.get("disk_write_mbps", 0.0))) / dt)
        self["cpu_window"].append(float(sample.get("cpu_percent", 0.0)))
        self["mem_window"].append(float(sample.get("mem_used_gb", 0.0)))
        self["sample"] = sample
        self["prev_ts"] = now
        self["updated_at"] = now

    def push_alert(self, alert: dict) -> None:
        """并入一条 /ws/monitor type=alert 事件（信封 payload，L16）。"""
        self["ws_alerts"].append(dict(alert))
        self["updated_at"] = time.monotonic()
