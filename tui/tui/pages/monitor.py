# -*- coding: utf-8 -*-
"""监控看板 · 星象台（方案 §3.4，MF1 最大欠账清偿）。

- KPI 行：CPU % / 内存 GB / 磁盘 MB/s / 运行任务数（等宽数字，1s WS 驱动，
  页面刷新节流 500ms）
- Sparkline 曲线：Textual Sparkline，窗口 60 点（CPU=极光青 / 内存=氢蓝）
- 进程表：本机 AstroForge 相关进程（PID/名称/环境/CPU/内存），运行行前置 ◈
- 告警区：内存阈值（>10GB 熔金 / >12GB nova，阈值取自 config-summary）+
  WS 通道告警；有未处理告警时 aurora-wash 底（静态，终端禁呼吸动画）
- 历史回放：range 胶囊 实时|1h|6h|24h（GET /monitor/history，整段重绘）

数据契约：/ws/monitor（app 层 1s 采集入 MonitorState）+ /api/v1/monitor/history。
进程表为本机 psutil 直采（服务核心无进程清单 API，TUI 与服务同机运行）。
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
    RadioButton,
    RadioSet,
    Sparkline,
    Static,
)
from textual.widgets.option_list import Option
from tui.theme.generated import tokens as design

WINDOW_POINTS = 60          # Sparkline 滚动窗口（方案 §3.4）
POLL_INTERVAL = 0.5         # KPI/曲线刷新节流 500ms
PROC_INTERVAL = 5.0         # 进程表扫描周期
REPO_ROOT = Path(__file__).resolve().parents[3]

# 模块 cli.py 路径段 → conda 环境名（进程表「环境」列推断；task_scheduler.MODULE_MAP 同源）
_MODULE_ENVS = {
    "spider": "env_spider", "mineru": "env_mineru", "wpd": "env_wpd",
    "anydoc": "env_anydoc", "md2docx": "env_md2docx",
}


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

    注：服务核心尚无 WS alert 事件广播（alerts 表未接路由），此处先由内存
    阈值与通道状态推导，服务端事件接入后并入同列。
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


class MonitorPage(VerticalScroll):
    """星象台：KPI + 曲线 + 进程表 + 告警 + 历史回放。"""

    def __init__(self, client, app_ref=None) -> None:  # noqa: ANN001（App 循环依赖）
        super().__init__(id="page-monitor")
        self.client = client
        self._app = app_ref
        self._range = "实时"
        self._alert_signature = ""

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
        yield RadioSet(
            *[RadioButton(label, value=(i == 0))
              for i, label in enumerate(("实时", "1h", "6h", "24h"))],
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
        self._render_alerts(derive_alerts(
            sample, state["warn_gb"], state["crit_gb"], state["ws_connected"],
        ))

    def _render_alerts(self, alerts: list[tuple[str, str]]) -> None:
        signature = "|".join(f"{level}:{text}" for level, text in alerts)
        if signature == self._alert_signature:
            return
        self._alert_signature = signature
        board = self.query_one("#mon-alerts", OptionList)
        board.clear_options()
        if not alerts:
            board.add_option(Option(
                f"[$aurora]{design.icon('status.ok')}[/$aurora] 星域平静 · 无告警",
                id="alert-none",
            ))
            board.remove_class("alerted")
            self.query_one("#mon-alerts-title", Static).update("[b]告警[/b]")
            return
        board.add_class("alerted")
        self.query_one("#mon-alerts-title", Static).update(
            f"[b]告警[/b]  [$molten]{len(alerts)} 条待处理[/$molten]"
            if all(level == "warn" for level, _ in alerts) else
            f"[b]告警[/b]  [$nova]{len(alerts)} 条待处理[/$nova]"
        )
        for index, (level, text) in enumerate(alerts):
            if level == "error":
                mark = f"[$nova]{design.icon('status.error')}[/$nova]"
            else:
                mark = f"[$molten]{design.icon('status.warn')}[/$molten]"
            board.add_option(Option(f" {mark} {text}", id=f"alert-{index}"))

    def _tick_procs(self) -> None:
        table = self.query_one("#mon-procs", DataTable)
        table.clear(columns=False)
        for row in scan_processes():
            prefix = (f"[dim]{design.icon('task.running')}[/dim] "
                      if row["module_task"] else "  ")
            table.add_row(
                str(row["pid"]), f"{prefix}{row['name']}", row["env"],
                f"{row['cpu']:.1f}", f"{row['mem_mb']:.0f}",
            )

    # ---- 历史回放（range 胶囊 → /monitor/history 整段重绘） ----
    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        label = str(event.pressed.label)
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

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        """告警行 Enter → 跳转任务历史（对齐「Enter 跳转对应任务」）。"""
        if event.option_id and event.option_id.startswith("alert-") and self._app is not None:
            self._app.switch_page(6)


class MonitorState(dict):
    """监控通道共享状态（app 层 WS worker 写入，状态栏与看板共读）。

    以 dict 子类承载便于直接下标读取；字段：
    sample/prev_ts/read_mbps/write_mbps/cpu_window/mem_window/ws_connected/
    running_count/warn_gb/crit_gb/updated_at
    """

    @classmethod
    def create(cls, warn_gb: float, crit_gb: float) -> MonitorState:
        return cls({
            "sample": None, "prev_ts": 0.0, "read_mbps": 0.0, "write_mbps": 0.0,
            "cpu_window": deque(maxlen=WINDOW_POINTS),
            "mem_window": deque(maxlen=WINDOW_POINTS),
            "ws_connected": False, "running_count": 0,
            "warn_gb": warn_gb, "crit_gb": crit_gb, "updated_at": 0.0,
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
