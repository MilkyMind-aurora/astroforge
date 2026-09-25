# -*- coding: utf-8 -*-
"""CLI 星幕渲染器（方案 §2.5 / §四）。

顶部「星空设计 token」段由 scripts/gen_design.py 生成（禁手改）；标记段之后的
渲染器手写区（banner/stage/progress/result_card/error_card/log 六件 + 错误码→
修复指引映射）随仓库提交，段替换不触及（tests/test_gen_design 有保留断言）。
降级纪律【硬性】：sys.stdout.isatty() 与 rich 可导入双检测，任一不满足 →
全部回退纯文本；stdout 日志行（``[INFO] ``/``[ERROR] `` 前缀）与结果 JSON
契约字节不变（服务核心逐行捕获零改动）。
"""
from __future__ import annotations

# ==== BEGIN 星空设计 token（scripts/gen_design.py 生成，禁手改）====
# 源：config/design/tokens.yaml + icons.yaml（sha256:06b559db8ba2）
# 消费：CLI 全部颜色/星符/动效节流一律取自本段（裸色/裸星符=违反设计契约）；
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
STAR_MOTION: dict[str, int] = {
    "progress_throttle_ms": 100,
    "spinner_frame_ms": 80,
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
    "task.pdf": "⬇",
    "task.table": "▦",
    "task.step_cursor": "▶",
    "misc.meteor": "☄",
    "misc.star_rank_1": "✦",
    "misc.star_rank_2": "✦✦",
    "misc.star_rank_3": "✧",
    "misc.binary_star": "✦✧",
    "misc.caret_down": "▾",
    "misc.caret_right": "▸",
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


# ============================================================
# 渲染器手写区（MF3 / V1-C.1）：六件套 + 错误码→修复指引映射
# ============================================================

import os  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

CORE_VERSION = "0.1.0"  # 横幅展示用，与 server/pyproject.toml version 同步
RULE_WIDTH = 60         # 阶段分隔线总宽（§4.1 样本量级；终端更窄时收缩）
CARD_MAX_WIDTH = 100    # §1.3：结果卡宽 = min(终端宽, 100)
PROGRESS_WIDTH = 40     # §1.3/§4.1：进度条 40 列
ITEM_LIMIT = 8          # 结果卡产物行上限（超出折叠为省略行，防刷屏）

# ---- 双检测【硬性】（§2.5）：TTY + rich 可导入，任一不满足 → 纯文本降级 ----


def _detect_tty() -> bool:
    """stdout 是否接终端（pytest 捕获/已关闭流一律按非 TTY 处理）。"""
    try:
        return bool(sys.stdout is not None and sys.stdout.isatty())
    except (AttributeError, ValueError, OSError):  # 捕获态/流已关闭
        return False


try:  # rich 为可选增强（§2.6：env_astroforge/env_spider 携带，其余模块环境降级）
    from rich.console import Console, Group
    from rich.panel import Panel
    from rich.progress import BarColumn, MofNCompleteColumn, Progress, TaskProgressColumn, TextColumn
    from rich.table import Table
    from rich.text import Text

    _RICH_OK = True
except ImportError:  # pragma: no cover - 取决于运行环境是否携带 rich
    Console = Group = Panel = Progress = BarColumn = MofNCompleteColumn = None  # type: ignore[assignment]
    TaskProgressColumn = TextColumn = Table = Text = None  # type: ignore[assignment]
    _RICH_OK = False

_STATE: dict[str, object] = {
    "plain": not (_detect_tty() and _RICH_OK),  # True = 纯文本降级态
    "theme": os.environ.get("ASTROFORGE_CLI_THEME", "dark"),  # deep-space 夜为主战场（§1.1）
    "force_color": os.environ.get("ASTROFORGE_CLI_FORCE_COLOR") == "1",  # 测试/样本生成用
}
_IS_TTY = _detect_tty()
_console: object | None = None      # rich Console 懒建（file=None 动态绑 sys.stdout，便于捕获）
_bar_state: dict[str, object] | None = None  # 进度条会话态（rich Progress 或 ASCII 条）


def configure(force_plain: bool | None = None, theme: str | None = None,
              force_color: bool | None = None) -> None:
    """运行态配置（测试/样本生成用）：可强制纯文本或强制着色，可切 dark/light 档。

    默认（不调用时）：plain = not (isatty and rich 可导入)；theme 取环境变量
    ASTROFORGE_CLI_THEME（默认 dark）。force_color 仅影响 rich Console 的
    force_terminal（供非 TTY 环境捕获 ANSI 样本），不改变降级判定本身。
    """
    global _console
    if force_plain is not None:
        _STATE["plain"] = force_plain
    if theme is not None:
        if theme not in STAR_TOKENS:
            raise ValueError(f"未知色彩档: {theme}（可选: {', '.join(sorted(STAR_TOKENS))}）")
        _STATE["theme"] = theme
    if force_color is not None:
        _STATE["force_color"] = force_color
    _console = None  # 下次输出按新配置重建 Console


def reset() -> None:
    """恢复默认运行态（测试隔离用）：重新双检测、theme 回环境变量默认。"""
    configure(
        force_plain=not (_detect_tty() and _RICH_OK),
        theme=os.environ.get("ASTROFORGE_CLI_THEME", "dark"),
        force_color=os.environ.get("ASTROFORGE_CLI_FORCE_COLOR") == "1",
    )


def _c(token: str) -> str:
    """当前档色值：一律取自生成段 STAR_TOKENS（裸色 = 违反设计契约）。"""
    current = palette(str(_STATE["theme"]))
    return current.get(token, current["ink-900"])


def _st(token: str, bold: bool = False) -> str:
    """rich 样式串（可选加粗）。"""
    base = _c(token)
    return f"bold {base}" if bold else base


def _ensure_console() -> Console:  # type: ignore[name-defined]
    """懒建 rich Console（file=None 动态绑定 sys.stdout；highlight 关闭防数字误染）。"""
    global _console
    if _console is None:
        _console = Console(
            file=None, highlight=False,
            force_terminal=True if _STATE["force_color"] else None,
        )
    return _console  # type: ignore[return-value]


def _emit(text: str) -> None:
    """纯文本输出（flush）。Windows 重定向到本地编码流时星符替换降级，绝不抛编码异常。"""
    try:
        print(text, flush=True)
    except UnicodeEncodeError:
        # 管道接 GBK 等本地编码时 ✦ 等字形不可编码：降级替换而非崩溃（服务调用不受影响）
        reconfigure = getattr(sys.stdout, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(errors="replace")
            print(text, flush=True)
        else:  # pragma: no cover - 捕获态 stdout 为 utf-8，不会抛编码异常
            print(text.encode("ascii", "replace").decode("ascii"), flush=True)


def _rich_line(spans: list[tuple[str, str | None]]) -> None:
    """富文本单行输出：spans = (文本, 样式) 列表；soft_wrap 禁折行（日志行 = 物理行）。"""
    text = Text()
    for chunk, style in spans:
        text.append(chunk, style=style or None)
    _ensure_console().print(text, soft_wrap=True)


# ------------------------------------------------------------
# log：stdout 日志唯一出口（字节契约所在）
# ------------------------------------------------------------

def log(level: str | None, msg: str) -> None:
    """分级日志行（§2.5：[INFO] 青灰 / [WARN] 熔金 / [ERROR] 朱红）。

    纯文本路径字节契约：``[{level}] {msg}\\n``，与 cli_utils 旧 print 实现逐字节
    一致（服务核心 process_runner 逐行捕获 + 行内 ``[ERROR]`` 判档零改动）。
    level=None 输出无前缀行（脚本标记行，如 ``[PASS] 健康检查``）。
    """
    text = f"[{level}] {msg}" if level else msg
    if _STATE["plain"] or not _RICH_OK:
        _emit(text)
        return
    prefix_style = {"INFO": _st("ink-600"), "WARN": _st("molten"),
                    "ERROR": _st("nova", bold=True)}.get(level or "")
    _rich_line([(f"[{level}] " if level else "", prefix_style), (msg, None)])


# ------------------------------------------------------------
# banner / stage：横幅与阶段分隔（§4.1 四段式的头两段）
# ------------------------------------------------------------

def banner(module: str, detail: str = "") -> None:
    """模块横幅：星符 + 「AstroForge · 衍星台 — 模块」+ 详情行；上下各 1 空行（§1.3）。

    银河渐变不在 CLI 白名单位（§1.1 whitelist 仅 TUI 启动屏/Flutter 完成横幅/AI
    抽屉饰线），横幅只做单色点睛：星符 aurora、题名 ink-900、副题 ink-600。
    """
    star = STAR_ICONS["nav.home"]
    title = f"AstroForge · 衍星台 — {module}"
    subtitle = f"Sidereal Core v{CORE_VERSION}" + (f" · {detail}" if detail else "")
    if _STATE["plain"] or not _RICH_OK:
        _emit("")
        _emit(f"  {star} {title}")
        _emit(f"  {subtitle}")
        _emit("")
        return
    console = _ensure_console()
    console.print()
    _rich_line([("  ", None), (star + " ", _st("aurora", bold=True)),
                (title, _st("ink-900", bold=True))])
    _rich_line([("  " + subtitle, _st("ink-600"))])
    console.print()


def stage(text: str, index: int | None = None, total: int | None = None) -> None:
    """阶段分隔线 + 阶段行（§4.1）：faint 横线居中星符；阶段行 = ◈ + 「阶段 i/N · text」。"""
    star = STAR_ICONS["nav.home"]
    label = text if index is None or total is None else f"阶段 {index}/{total} · {text}"
    mid = f" {star} "
    left = (RULE_WIDTH - len(mid)) // 2
    rule = "─" * left + mid + "─" * (RULE_WIDTH - len(mid) - left)
    icon = STAR_ICONS["task.running"]
    if _STATE["plain"] or not _RICH_OK:
        _emit(rule)
        _emit(f"{icon} {label}")
        return
    _rich_line([(rule[:left], _st("faint")), (mid, _st("aurora")),
                (rule[left + len(mid):], _st("faint"))])
    _rich_line([(icon + " ", _st("aurora")), (label, _st("ink-900", bold=True))])


# ------------------------------------------------------------
# progress：任务进度（rich Progress / ASCII 条；非 TTY 静默）
# ------------------------------------------------------------

def progress(done: int, total: int, label: str = "进度") -> None:
    """任务进度（§2.5）：rich 可用走 rich Progress；TTY 无 rich 走 ASCII ``█░`` 条。

    非 TTY（服务核心管道捕获）静默：管道里 ``\\r`` 重绘会污染逐行捕获，进度信息
    由逐条 ``[INFO] `` 行与结果 JSON 承担，stdout 契约不增噪。刷新节奏取
    tokens motion.cli.progress_throttle_ms（rich: refresh_per_second；ASCII: 时间节流）。
    """
    if total <= 0:
        return
    if not (_IS_TTY or _STATE["force_color"]):
        return  # 非 TTY：静默（理由见 docstring）
    if _STATE["plain"] or not _RICH_OK:
        _ascii_progress(done, total, label)
    else:
        _rich_progress(done, total, label)


def progress_end() -> None:
    """收尾未完成的进度条（失败路径用；成功路径 done>=total 时自动收尾）。"""
    global _bar_state
    if _bar_state is None:
        return
    if _bar_state.get("kind") == "rich":
        _bar_state["progress"].stop()  # type: ignore[union-attr]
    elif _IS_TTY:
        sys.stdout.write("\n")
        sys.stdout.flush()
    _bar_state = None


def _ascii_progress(done: int, total: int, label: str) -> None:
    """TTY 无 rich：``█░`` 条 + 计数行，按 tokens 节流逐行输出。

    刻意不做 ``\\r`` 原地重绘：与逐行日志交错时会把后续行粘连到条尾（rich 态由
    Live 解决，ASCII 态的最忠实降级是独立成行，对齐 §4.1 样本布局）。
    """
    global _bar_state
    now = time.monotonic()
    throttle = STAR_MOTION.get("progress_throttle_ms", 100) / 1000
    finished = done >= total
    if not finished and _bar_state is not None and now - float(_bar_state["t"]) < throttle:
        return
    filled = round(PROGRESS_WIDTH * done / total)
    bar = "█" * filled + "░" * (PROGRESS_WIDTH - filled)
    _emit(f"{label}  {bar}  {done}/{total} · {done / total * 100:.0f}%")
    _bar_state = {"kind": "ascii", "t": now} if not finished else None


def _rich_progress(done: int, total: int, label: str) -> None:
    """TTY + rich：transient Progress（结束时自动清行，不在回滚缓冲留残影）。"""
    global _bar_state
    if _bar_state is None or _bar_state.get("kind") != "rich":
        throttle = STAR_MOTION.get("progress_throttle_ms", 100)
        progress_obj = Progress(
            TextColumn(f"{label} "),
            BarColumn(bar_width=PROGRESS_WIDTH, complete_style=_c("aurora"),
                      finished_style=_c("aurora"), pulse_style=_c("nebula")),
            TextColumn("· "), MofNCompleteColumn(), TextColumn("· "), TaskProgressColumn(),
            console=_ensure_console(), transient=True,
            refresh_per_second=max(1, round(1000 / throttle)),
        )
        progress_obj.start()
        _bar_state = {"kind": "rich", "progress": progress_obj,
                      "task": progress_obj.add_task(label, total=total)}
    progress_obj = _bar_state["progress"]  # type: ignore[assignment]
    task_id = _bar_state["task"]  # type: ignore[assignment]
    # refresh=True：每次更新立即重绘（调用频率本身受 tokens 节流约束）
    progress_obj.update(task_id, completed=done, total=total, refresh=True)  # type: ignore[union-attr]
    if done >= total:
        progress_obj.stop()  # type: ignore[union-attr]
        _bar_state = None


# ------------------------------------------------------------
# result_card / error_card：收尾两卡（§4.1 四段式的尾段）
# ------------------------------------------------------------

def result_card(title: str, items: list[tuple[str, str]] | None = None,
                note: str = "", section: str = "产物") -> None:
    """结果卡（§4.1）：✓ 标题（可附 note）+ 产物行「✦ 名称  详情」。

    rich：aurora 边框 Panel，宽 = min(终端宽, 100)；纯文本：无边框缩进行
    （对齐依赖等宽终端，避免手绘盒线在变宽字体下错位）。
    """
    rows = list(items or [])
    star = STAR_ICONS["nav.home"]
    if _STATE["plain"] or not _RICH_OK:
        # 纯文本路径不触碰任何 rich 类型（无 rich 环境下 Text/Panel 均不可用）
        _emit(f"{STAR_ICONS['task.success']} {title}" + (f" · {note}" if note else ""))
        if rows:
            _emit(f"  {section} {len(rows)} 项：")
            for name, detail in rows:
                _emit(f"    {star} {name}" + (f"  {detail}" if detail else ""))
        return
    title_text = Text()
    title_text.append(f"{STAR_ICONS['task.success']} ", style=_st("aurora", bold=True))
    title_text.append(title, style=_st("ink-900", bold=True))
    if note:
        title_text.append(f" · {note}", style=_st("ink-600"))
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style=_st("ink-900"))
    grid.add_column(style=_st("ink-600"), ratio=1)
    for name, detail in rows:
        grid.add_row(f"{star} {name}", detail or "")
    body: object = grid if rows else Text("")
    if rows:
        body = Group(Text(f"{section} {len(rows)} 项：", style=_st("ink-600")), grid)
    console = _ensure_console()
    console.print(Panel(body, title=title_text, title_align="left",
                        border_style=_st("aurora"),
                        width=min(console.width, CARD_MAX_WIDTH)))


def error_card(code: int, message: str, guide: str | None = None) -> None:
    """错误卡（§4.1）：nova 红边框 + 「✕ 失败 · code N」+ 信息 + 修复指引（pro 7.3.2 映射）。"""
    guide = fix_guide(code) if guide is None else guide
    if _STATE["plain"] or not _RICH_OK:
        _emit(f"{STAR_ICONS['status.error']} 失败 · code {code}")
        _emit(f"  {message}")
        _emit(f"  修复指引: {guide}")
        return
    title_text = Text(f"{STAR_ICONS['status.error']} 失败 · code {code}",
                      style=_st("nova", bold=True))
    body = Text()
    body.append(message + "\n", style=_st("ink-900"))
    body.append("修复指引: " + guide, style=_st("molten"))
    console = _ensure_console()
    console.print(Panel(body, title=title_text, title_align="left",
                        border_style=_st("nova"),
                        width=min(console.width, CARD_MAX_WIDTH)))


# ------------------------------------------------------------
# 错误码 → 修复指引映射表（pro 7.3.2；码段语义见 pro §3.8 统一错误码分段）
# ------------------------------------------------------------

ERROR_GUIDES: dict[int, str] = {
    1001: "检查任务配置：补全缺失参数（task_type/url/input_path 等，字段见各模块 cli.py 文档串）",
    1002: "检查输入合法性：外联 URL 仅允许 http/https（经 url_guard 校验）；文件格式需在模块支持清单内",
    1003: "模板名不合法：查询 GET /api/v1/templates 可用模板清单后重试",
    1004: "流水线 YAML 解析失败：核对缩进与字段名，经流水线页「自定义 YAML」重新保存",
    1300: "任务已按请求取消，无需修复；需要时重新创建任务即可",
    2001: "认证失败：请求头补 X-AstroForge-Token（token 见 data/service_token）",
    2002: "服务内部错误：查 data/logs/ 与服务核心日志定位；必要时重启 Sidereal Core",
    2003: "配置缺失：检查 config/settings.yaml 与环境变量（ASTROFORGE_PG_PASSWORD 等）",
    2004: "数据库不可用：确认 PostgreSQL 已启动、astroforge 库已建（scripts/db_init.sql）",
    3001: "运行环境缺失：运行 scripts/install_envs*.bat|.sh 创建对应 conda 环境，scripts/check_env.* 复查",
    3002: "子进程超时：放大任务超时配置或缩减输入规模后重试",
    3003: "模块执行异常：查看任务日志尾部 stderr 定位；修复后可直接重试该任务",
    3004: "疑似反爬拦截：调大 request_interval、配置 browser.chromium_path 走本地渲染后重试",
    3005: "模型加载失败：运行 scripts/download_models.* 补齐模型文件，确认 env_ai 已装 llama-cpp-python",
    3006: "该功能属规划内未实现（Phase 2）：当前改用其他任务类型，等待后续版本",
    4001: "输入不存在：核对 input_path/input_dir 是否存在且可读",
    4002: "内存超红线（settings.system.max_memory_gb）：调小 max_threads/批量规模后重试",
    4003: "磁盘空间不足：清理 data/ 与模块输出目录后重试",
    4004: ("依赖缺失：anydoc 二进制缺失运行 scripts/install_anydoc.bat|.sh；"
           "AI 引擎未启动则拉起 modules/ai_engine"),
}

_SEGMENT_GUIDES: dict[int, str] = {
    1: "客户端参数错误：核对任务配置字段与取值范围（1xxx 段）",
    2: "服务端错误：查服务核心日志与 data/logs/（2xxx 段）",
    3: "模块执行错误：查任务日志尾部与对应 conda 环境（3xxx 段）",
    4: "资源错误：核对文件/内存/磁盘/依赖进程状态（4xxx 段）",
}


def fix_guide(code: int) -> str:
    """错误码 → 修复指引（未登记码回落分段指引；0 = 成功无需修复）。"""
    if code == 0:
        return "任务成功，无需修复"
    guide = ERROR_GUIDES.get(code)
    if guide:
        return guide
    return _SEGMENT_GUIDES.get(code // 1000, "未登记错误码：查 docs/ 与任务日志定位")


# ------------------------------------------------------------
# shell 脚本横幅入口（start_service/check_env/db_backup/install_* 共用）
# ------------------------------------------------------------

def _main(argv: list[str] | None = None) -> int:
    """用法：python modules/_shared/star_console.py banner <module> [detail]"""
    import argparse

    parser = argparse.ArgumentParser(description="AstroForge CLI 星幕渲染器（shell 脚本横幅入口）")
    sub = parser.add_subparsers(dest="command", required=True)
    banner_parser = sub.add_parser("banner", help="打印模块横幅（纯文本/富文本按双检测自动降级）")
    banner_parser.add_argument("module", help="模块/脚本名")
    banner_parser.add_argument("detail", nargs="?", default="", help="副题（环境/用途）")
    args = parser.parse_args(argv)
    banner(args.module, args.detail)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
