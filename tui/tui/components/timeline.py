# -*- coding: utf-8 -*-
"""流水线步骤时间线（方案 §3.4 / 星空规格 v1 §三.5 组件规格的 TUI 落地）。

垂直步骤条 `○─爬取章节`/`◈─▶ 转换 DOCX`/`●─✓ …`；运行步骤帧动画 ◈◉（0.6s，
唯一循环位，Modal 弹出时由 Textual 定时器照常但不产生额外通道——终端性能
红线约束下的最小动画）；完成瞬间 just-done 提亮 160ms（#11 过冲的 TUI 离散
近似：先亮后定）；失败步骤 nova 红 + 行 wash + 「重试该步」钮（V1.1-6 步骤级
续跑契约 POST /tasks/{uuid}/steps/{i}/retry，语义=前序产物保留原地续跑）。
"""
from __future__ import annotations

from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Static

from tui.theme.generated import tokens as design

FRAME_INTERVAL_S = 0.6   # 运行帧 ◈◉（icons.yaml task.running/_f2，1.2s 一循环）
FLASH_S = 0.16           # 完成提亮（对齐 #10 推满提亮时长）

# 步骤状态 → (节点星符语义名, 色名)；pending=○ ink-400 / running=◈ aurora /
# success=● aurora / failed=✕ nova（✓ 状态字形在行内单独渲染）
NODE_META: dict[str, tuple[str, str]] = {
    "pending": ("task.pending", "ink-400"),
    "running": ("task.running", "aurora"),
    "success": ("status.ok", "aurora"),
    "failed": ("task.failed", "nova"),
}


def render_step(step: dict, running_frame: int = 0) -> str:
    """单步行渲染（确定性纯函数，单测覆盖）。

    `○─ 名称`（待运行）· `◈─▶ 名称`（运行中）· `●─✓ 名称`（完成）·
    `✕─✕ 名称`（失败，nova）。星符全部经 icons.yaml 语义名。
    """
    status = str(step.get("status", "pending"))
    name = str(step.get("step_name", "?"))
    node_icon, color = NODE_META.get(status, NODE_META["pending"])
    if status == "running":
        node = design.icon("task.running" if running_frame % 2 == 0 else "task.running_f2")
        glyph = f"[${color}]{design.icon('task.step_cursor')}[/${color}] "
    elif status == "success":
        node = design.icon(node_icon)
        glyph = f"[${color}]{design.icon('task.success')}[/${color}] "
    elif status == "failed":
        node = design.icon(node_icon)
        glyph = f"[${color}]{design.icon('task.failed')}[/${color}] "
    else:
        node = design.icon(node_icon)
        glyph = ""
    return f"[${color}]{node}[/${color}]─{glyph}{name}"


class StepTimeline(Vertical):
    """步骤时间线容器：set_steps() 就地重建行（数据来自 GET /tasks/{uuid} steps）。"""

    DEFAULT_CSS = """
    StepTimeline { height: auto; border: round $border-subtle; background: $card;
        padding: 0 1; margin-top: 1; }
    StepTimeline .step-line { color: $ink-900; }
    StepTimeline .step-row.just-done .step-line { text-style: bold; }
    StepTimeline .step-row.failed { background: $errorWashBg; }
    StepTimeline .step-retry { height: 1; min-width: 10; border: none;
        background: transparent; color: $nova; text-align: right; }
    StepTimeline .step-title { color: $ink-600; }
    """

    class StepRetried(Message):
        """失败步骤已请求续跑（父页面据此刷新任务详情）。"""

        def __init__(self, timeline: "StepTimeline", task_uuid: str, step_index: int) -> None:
            super().__init__()
            self.timeline = timeline
            self.task_uuid = task_uuid
            self.step_index = step_index

    def __init__(self, client, task_uuid: str, steps: list[dict],
                 title: str = "步骤时间线", allow_retry: bool = True) -> None:
        super().__init__()
        self.client = client
        self.task_uuid = task_uuid
        self._steps: list[dict] = list(steps)
        self._title = title
        self._allow_retry = allow_retry
        self._frame = 0

    def compose(self):
        yield Static(f"[dim]{self._title}[/dim]", classes="step-title")
        for index, step in enumerate(self._steps):
            with Horizontal(classes="step-row", id=f"step-row-{index}"):
                yield Static(render_step(step), classes="step-line")
                if self._allow_retry and step.get("status") == "failed":
                    yield Button(
                        f"重试该步 {design.icon('task.step_cursor')}",
                        id=f"step-retry-{index}", classes="step-retry")

    def on_mount(self) -> None:
        self.set_interval(FRAME_INTERVAL_S, self._advance_frame)

    # ---- 对外入口 ----
    @property
    def steps(self) -> list[dict]:
        return self._steps

    async def set_steps(self, steps: list[dict]) -> None:
        """更新步骤集：行数一致就地刷新；行数变化（含 0→N 首填）整段重建。

        running→success 瞬间提亮 160ms（#11 过冲的 TUI 离散近似）。
        """
        old_status = {i: str(s.get("status")) for i, s in enumerate(self._steps)}
        self._steps = list(steps)
        rows = list(self.query(".step-row"))
        if len(rows) != len(self._steps):
            for row in rows:
                await row.remove()
            for index, step in enumerate(self._steps):
                row = Horizontal(classes="step-row", id=f"step-row-{index}")
                await self.mount(row)
                await row.mount(Static(render_step(step, self._frame),
                                       classes="step-line"))
                if self._allow_retry and step.get("status") == "failed":
                    await row.mount(Button(
                        f"重试该步 {design.icon('task.step_cursor')}",
                        id=f"step-retry-{index}", classes="step-retry"))
            return
        for index, step in enumerate(self._steps):
            row = self.query_one(f"#step-row-{index}", Horizontal)
            line = row.query_one(".step-line", Static)
            line.update(render_step(step, self._frame))
            retry_button = row.query(".step-retry")
            if self._allow_retry and step.get("status") == "failed" and not retry_button:
                await row.mount(Button(
                    f"重试该步 {design.icon('task.step_cursor')}",
                    id=f"step-retry-{index}", classes="step-retry"))
            elif step.get("status") != "failed" and retry_button:
                for button in retry_button:
                    await button.remove()  # 步骤离开失败态：撤掉重试钮
            if old_status.get(index) == "running" and step.get("status") == "success":
                # #11 完成过冲的 TUI 离散近似：先亮 160ms 再落定
                row.add_class("just-done")
                row.set_timer(FLASH_S, lambda r=row: r.remove_class("just-done"))

    # ---- 内部 ----
    def _advance_frame(self) -> None:
        self._frame += 1
        for index, step in enumerate(self._steps):
            if step.get("status") == "running":
                self.query_one(f"#step-row-{index}", Horizontal).query_one(
                    ".step-line", Static).update(render_step(step, self._frame))

    async def _do_retry(self, step_index: int) -> None:
        try:
            record = await self.client.retry_step(self.task_uuid, step_index)
        except Exception as exc:
            self.app.notify(f"步骤续跑请求失败：{exc}", severity="error")
            return
        if record is None:
            self.app.notify("步骤不可续跑（仅失败任务的失败步骤）", severity="warning")
            return
        self.post_message(self.StepRetried(self, self.task_uuid, step_index))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("step-retry-"):
            event.stop()  # 不冒泡到父页面按钮处理器
            self.run_worker(self._do_retry(int(button_id.rsplit("-", 1)[1])),
                            exclusive=True)
