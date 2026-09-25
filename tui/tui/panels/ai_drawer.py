# -*- coding: utf-8 -*-
"""星伴 AI 抽屉（方案 §3.6，MF2 重写，替换 MF1 居中 Modal 版 AiPanel）。

形态：右侧 60% 宽抽屉（非居中 Modal，反面清单红线）；头部 nebula 竖饰线 +
模型胶囊（qwen2b/ornith9b，切换走 POST /ai/model/switch 代理，引擎忙/不可达
置灰）；消息区重构——用户行 `› 你：…` 右对齐 ink-600，星伴回复**无框纯文本**
ink-900（Kimi 式无气泡【K4 3.2】），流式 #5 合批 append（RichLog 增量写，
2~4 token/帧，禁整块重排）；思考态 `✶ 思忖中…` 帧动画 ✶✷✸（#6，1.2s 循环）；
指令卡生长式（#12 TUI 离散近似：逐行显现）；追问 chips 三枚（引擎无追问返回，
本地模板兜底）。
主题取色：RichLog 滚动缓冲不随主题重渲，行样式经 design.THEME_PALETTE 按
当前主题取 token hex（生成物常量，禁裸色，§3.7 门禁①）。
"""
from __future__ import annotations

import asyncio
import json

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.geometry import Offset
from textual.screen import Screen
from textual.widgets import Button, Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from tui.components.theme import rich_line, theme_token
from tui.service_client import ServiceClient
from tui.theme.generated import tokens as design

STREAM_BATCH_CHARS = 3      # 每帧合批 2~4 token（CJK 1 字≈1 token，T_STREAM）
STREAM_FLUSH_S = 0.05       # 20fps × 3 字 ≈ 60 token/s
THINK_FRAMES = ("ai.thinking", "ai.thinking_f2", "ai.thinking_f3")
THINK_INTERVAL_S = 0.4      # ✶✷✸ 1.2s 一循环（#6）
GROW_STEP_S = 0.06          # 指令卡生长式逐行间隔（#12 TUI 离散近似）
SLIDE_S_KEY = "t_slide"     # T_SLIDE out_cubic（§1.4）

# 模型胶囊清单（服务端 KNOWN_MODELS 同源；定位文案对齐方案 §5.6 模型弹层）
MODELS: tuple[tuple[str, str], ...] = (
    ("qwen2b", "常驻 · 日常指令"),
    ("ornith9b", "按需 · 复杂拆解 · ≈5.6GB"),
)
# 追问 chips 本地兜底模板（服务端 ai_done 无追问字段，方案允许本地兜底）
FOLLOWUPS: tuple[str, ...] = (
    "把刚才的结果转成 Word",
    "解析我最近下载的 PDF",
    "看看当前任务进度",
)


def take_batch(buffer: str, size: int = STREAM_BATCH_CHARS) -> tuple[str, str]:
    """流式合批取样（纯函数，单测覆盖）：返回 (本帧上屏文本, 剩余缓冲)。"""
    if size <= 0 or not buffer:
        return "", buffer
    return buffer[:size], buffer[size:]


_theme_token = theme_token  # 面板内部沿用旧短名（取色语义见 components.theme）


def _model_check(key: str, current: str) -> str:
    """当前档 ✓ 前缀（OptionList 行内 markup，$变量随主题热切）。"""
    return (f"[${'aurora'}]{design.icon('task.success')}[/$aurora]"
            if key == current else "   ")


class ModelSheet(Screen):
    """模型选择弹层（§5.6 与 Kimi 模型弹层同构的 TUI 落地：盒式 OptionList）。"""

    CSS = """
    ModelSheet { align: center middle; background: $scrim; }
    #model-box { width: 52; height: auto; border: round $border-active;
        background: $cardRaised; padding: 0 1; }
    #model-title { color: $ink-900; padding-bottom: 1; }
    #model-list { height: auto; max-height: 8; }
    """

    def __init__(self, current: str) -> None:
        super().__init__()
        self._current = current

    def compose(self) -> ComposeResult:
        with Vertical(id="model-box"):
            yield Static(f"{design.icon('ai.idle')} 选择星伴模型", id="model-title")
            yield OptionList(*[
                Option(
                    f"{_model_check(key, self._current)} {key}  [dim]{caption}[/dim]",
                    id=key,
                )
                for key, caption in MODELS
            ], id="model-list")

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(event.option_id)


class AiDrawerScreen(Screen):
    """星伴 AI 右抽屉：A / Ctrl+Shift+A 唤起，Esc 逐层退出。"""

    CSS = """
    AiDrawerScreen { align: right middle; }
    #ai-box { width: 60%; min-width: 56; height: 100%; border-left: thick $nebula;
        background: $card; padding: 0 2; }
    #ai-head { height: 1; color: $ink-900; margin-top: 1; }
    #ai-meta { height: auto; margin-bottom: 1; }
    #ai-model-btn { min-width: 18; height: 1; border: none; background: $aiContainerBg;
        color: $nebula; text-align: center; }
    #ai-model-btn:hover { background: $containerPressed; }
    #ai-engine { color: $ink-400; margin-left: 1; }
    #ai-out { height: 1fr; border: round $border-subtle; background: $sunken;
        padding: 0 1; margin-bottom: 1; }
    #ai-think { height: 1; color: $nebula; display: none; }
    #ai-think.thinking-on { display: block; opacity: $thinking-opacity; }
    #ai-followups { height: auto; display: none; }
    #ai-followups.followups-on { display: block; }
    #ai-followups Button { height: 3; margin-right: 1; border: none;
        background: $container; color: $ink-600; }
    #ai-followups Button:hover { background: $containerPressed; color: $ink-900; }
    #ai-status { height: 1; color: $ink-400; }
    """

    BINDINGS = [Binding("escape", "dismiss_panel", "关闭", show=False)]

    def __init__(self, client: ServiceClient) -> None:
        super().__init__()
        self.client = client
        self.conversation_id: int | None = None
        self._busy = False
        self._buffer = ""          # 待上屏流式缓冲（合批源）
        self._model_key = MODELS[0][0]
        self._switching = False

    def compose(self) -> ComposeResult:
        with Vertical(id="ai-box"):
            yield Static(
                f"[${'nebula'}]{design.icon('ai.idle')}[/$nebula] [b]星伴[/b]"
                f"  [dim]Sidereal 本地引擎 · 数据不出本机[/dim]", id="ai-head")
            with Horizontal(id="ai-meta"):
                yield Button(f"{self._model_key} {design.icon('misc.caret_down')}",
                             id="ai-model-btn")
                yield Static("", id="ai-engine")
            with VerticalScroll(id="ai-out"):
                yield RichLog(id="ai-log", markup=False, wrap=True, highlight=False)
            yield Static("", id="ai-think")
            with Horizontal(id="ai-followups"):
                for index, text in enumerate(FOLLOWUPS):
                    yield Button(text, id=f"followup-{index}")
            yield Static("", id="ai-status")
            yield Input(placeholder="输入消息，回车发送（Esc 关闭抽屉）", id="ai-in")

    def on_mount(self) -> None:
        log_widget = self.query_one("#ai-log", RichLog)
        log_widget.write(Text(
            "问我「把 Vue 文档爬下来转 Word」试试。星伴会把自然语言解析成任务指令。",
            style=_theme_token(self.app, "ink-400")))
        self.run_worker(self._probe_engine(), exclusive=True)
        # 抽屉滑入（T_SLIDE out_cubic）：入场一次性位移动画（§1.4）
        box = self.query_one("#ai-box", Vertical)
        box.styles.offset = Offset(int(self.app.size.width * 0.6), 0)
        box.animate("offset", Offset(0, 0), duration=design.MOTION_TUI[SLIDE_S_KEY]
                    ["duration_ms"] / 1000, easing=design.MOTION_TUI[SLIDE_S_KEY]["easing"])

    # ---- 引擎状态与模型胶囊 ----
    async def _probe_engine(self) -> None:
        engine = self.query_one("#ai-engine", Static)
        try:
            status = await self.client.engine_status()
        except Exception as exc:
            engine.update(f"[$nova]{design.icon('status.error')} 引擎探测失败[/] {exc}")
            return
        if not status.get("reachable"):
            engine.update(f"[$molten]{design.icon('status.warn')} 引擎休眠中[/] "
                          "（表单路径不受影响，发送消息将等待唤醒）")
            return
        current = str(status.get("current_model") or self._model_key)
        self._model_key = current if any(key == current for key, _ in MODELS) else self._model_key
        self._render_model_btn()
        engine.update(f"[$aurora]{design.icon('status.ok')}[/] {current}")

    def _render_model_btn(self) -> None:
        self.query_one("#ai-model-btn", Button).label = (
            f"{self._model_key} {design.icon('misc.caret_down')}")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "ai-model-btn":
            self._open_model_sheet()
        elif button_id.startswith("followup-"):
            index = int(button_id.rsplit("-", 1)[1])
            self._send(FOLLOWUPS[index])

    def _open_model_sheet(self) -> None:
        if self._switching:
            return

        def apply(model_key: str | None) -> None:
            if model_key is not None:
                self.run_worker(self._switch_model(model_key), exclusive=True)

        self.app.push_screen(ModelSheet(self._model_key), apply)

    async def _switch_model(self, model_key: str) -> None:
        status = self.query_one("#ai-status", Static)
        self._switching = True
        status.update(f"切换模型到 {model_key}…（首载 9B 需等待）")
        try:
            await self.client.switch_model(model_key)
        except Exception as exc:
            status.update(f"[$nova]切换失败[/] {exc}")
        else:
            self._model_key = model_key
            self._render_model_btn()
            status.update(f"[$aurora]{design.icon('task.success')}[/] 已切换到 {model_key}")
            await asyncio.sleep(2.0)
            status.update("")
        finally:
            self._switching = False

    # ---- 发送与流式渲染 ----
    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text:
            self._send(text)

    def _send(self, text: str) -> None:
        if self._busy:
            self.query_one("#ai-status", Static).update("星伴正在回复，稍候…")
            return
        input_widget = self.query_one("#ai-in", Input)
        input_widget.value = ""
        self.query_one("#ai-followups", Horizontal).remove_class("followups-on")
        self.run_worker(self._stream_chat(text), exclusive=False)

    def _write_user(self, message: str) -> None:
        """用户行：`› 你：…` 右对齐（Rich Text justify，§3.6）。"""
        self.query_one("#ai-log", RichLog).write(Text(
            f"› 你：{message}", justify="right",
            style=_theme_token(self.app, "ink-600")))

    async def _stream_chat(self, message: str) -> None:
        """WS /ws/ai 流式对话：ai_delta 入缓冲，定时器合批增量 append（禁整块重排）。"""
        log_widget = self.query_one("#ai-log", RichLog)
        status = self.query_one("#ai-status", Static)
        think = self.query_one("#ai-think", Static)
        self._busy = True
        self._buffer = ""
        self._write_user(message)
        think.add_class("thinking-on")
        think_timer = self.set_interval(THINK_INTERVAL_S, self._cycle_think)
        flush = self.set_interval(STREAM_FLUSH_S, self._flush)
        status.update("思忖中…")
        import websockets

        base = self.client.base_url.replace("http", "ws")
        try:
            async with websockets.connect(
                f"{base}/ws/ai?token={self.client.token}"
            ) as ws:
                await ws.send(json.dumps({
                    "message": message,
                    **({"conversation_id": self.conversation_id}
                       if self.conversation_id is not None else {}),
                }, ensure_ascii=False))
                while True:
                    frame = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
                    ftype = frame.get("type")
                    payload = frame.get("payload") or {}
                    if ftype == "ai_delta":
                        self._buffer += str(payload.get("text", ""))
                        think.remove_class("thinking-on")
                        status.update("生成中…")
                    elif ftype == "ai_done":
                        flush.stop()
                        think_timer.stop()
                        self._drain_buffer(log_widget)
                        self.conversation_id = payload.get("conversation_id")
                        think.remove_class("thinking-on")
                        status.update("")
                        await self._render_done(log_widget, payload)
                        return
                    elif ftype == "ai_error":
                        flush.stop()
                        think_timer.stop()
                        self._drain_buffer(log_widget)
                        think.remove_class("thinking-on")
                        message_text = str(payload.get("message", "引擎错误"))
                        log_widget.write(Text(
                            f"✕ {message_text}", style=_theme_token(self.app, "nova")))
                        status.update("")
                        return
        except Exception as exc:
            flush.stop()
            think_timer.stop()
            self._drain_buffer(log_widget)
            think.remove_class("thinking-on")
            log_widget.write(Text(
                f"✕ 流式通道失败：{exc}", style=_theme_token(self.app, "nova")))
            status.update("")
        finally:
            self._busy = False

    def _flush(self) -> None:
        """合批上屏（#5）：每帧最多 3 token 增量 append，缓冲空时不写。"""
        if not self._buffer:
            return
        chunk, self._buffer = take_batch(self._buffer)
        self.query_one("#ai-log", RichLog).write(
            Text(chunk, style=_theme_token(self.app, "ink-900")), end="")

    def _drain_buffer(self, log_widget: RichLog) -> None:
        if self._buffer:
            log_widget.write(Text(
                self._buffer, style=_theme_token(self.app, "ink-900")), end="")
            self._buffer = ""
        log_widget.write("")  # 换行收尾

    def _cycle_think(self) -> None:
        """思考帧动画（#6）：✶✷✸ 1.2s 循环 + 思忖文案。"""
        self._think_frame = getattr(self, "_think_frame", 0) + 1
        glyph = design.icon(THINK_FRAMES[self._think_frame % len(THINK_FRAMES)])
        self.query_one("#ai-think", Static).update(
            f"[${'nebula'}]{glyph}[/$nebula] 思忖中…")

    async def _render_done(self, log_widget: RichLog, payload: dict) -> None:
        """ai_done：指令卡生长式（逐行显现，#12 TUI 离散近似）+ 追问 chips。"""
        instruction = payload.get("instruction")
        if not instruction:
            self.query_one("#ai-followups", Horizontal).add_class("followups-on")
            return
        task_type = instruction.get("task_type", "?")
        params = instruction.get("params", {})
        key_param = str(params.get("url") or params.get("input_path")
                        or params.get("pipeline") or "")[:40]
        lines: list[list[tuple[str, str | None]]] = [
            [("╭─", "ink-600"), (design.icon("nav.task") + " 已解析任务", "hydrogen"),
             ("─", "ink-600")],
            [(f"{task_type}  ", "ink-900"), (key_param, "ink-400")],
        ]
        if payload.get("task_uuid"):
            lines.append([
                (design.icon("task.success") + " 已创建任务 "
                 f"{str(payload['task_uuid'])[:8]}", "aurora"),
                ("（Ctrl+` 看日志）", "ink-400"),
            ])
        if payload.get("notice"):
            lines.append([(str(payload["notice"]), "molten")])
        lines.append([("╰─" + "─" * 24, "ink-600")])
        for delay, segments in enumerate(lines):  # 生长式：逐行显现
            self.set_timer(
                GROW_STEP_S * delay,
                lambda segs=segments: log_widget.write(rich_line(self.app, segs)))
        await asyncio.sleep(GROW_STEP_S * len(lines))
        self.query_one("#ai-followups", Horizontal).add_class("followups-on")

    def action_dismiss_panel(self) -> None:
        self.dismiss()
