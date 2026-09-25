# -*- coding: utf-8 -*-
"""流水线 · NovaFlow 时间线（方案 §3.4，MF2 升级）。

模板 OptionList 卡（名称+场景描述+步骤数）→ 运行视图=步骤时间线
（components.timeline：运行步骤 ◈◉ 帧动画 / 完成过冲提亮 / 失败步骤 nova 红
+ 单步重试——V1.1-6 步骤级续跑契约，语义=「从步骤 N 继续（前序产物已保留）」，
续跑原地更新同一任务）；YAML 粘贴保存自定义模板保留（折叠区）。
数据契约：POST /pipelines/{name}/run → 订阅 /ws/logs/{uuid} 的 status/progress
事件驱动时间线与进度条；GET /tasks/{uuid} 拉取 steps 快照。
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Button, OptionList, Static, TextArea
from textual.widgets.option_list import Option

from tui.components.task_card import TaskProgressCard
from tui.components.timeline import StepTimeline
from tui.service_client import ServiceClient
from tui.theme.generated import tokens as design

STEPS_REFRESH_S = 2.0  # 运行时间线轮询周期（steps 无独立 WS 事件，详情轮询补齐）


class PipelinePage(VerticalScroll):
    """流水线：模板选择运行 + 运行时间线 + YAML 保存为自定义模板。"""

    CSS = """
    #pl-form { border: round $border-subtle; background: $card; padding: 0 2;
        margin-top: 1; }
    #pl-title { color: $ink-900; margin-top: 1; }
    #pl-list { height: auto; max-height: 8; border: round $border-subtle;
        background: $sunken; }
    #pl-run { width: 100%; margin-top: 1; }
    #pl-yaml-box Input, #pl-yaml { border: round $border-subtle; }
    #pl-yaml { height: 8; background: $sunken; }
    #pl-save { margin-top: 1; }
    """

    def __init__(self, client: ServiceClient, app_ref=None) -> None:  # noqa: ANN001
        super().__init__(id="page-pipeline")
        self.client = client
        self._pipelines: list[dict] = []
        self._task_uuid: str | None = None
        self._active = False


    async def _auto_reload_steps(self) -> None:
        if self._active and self._task_uuid:
            await self._reload_steps()

    def compose(self) -> ComposeResult:
        yield Static(
            f"[b]{design.icon('nav.pipeline')} 流水线[/b]  "
            f"[dim]NovaFlow 编排引擎 · 断点续跑（失败步骤可单独重试）[/dim]",
            id="pl-title", classes="page-body")
        with Vertical(id="pl-form"):
            yield Static("模板（内置 + 自定义）", classes="page-body")
            yield Static("加载模板中…", id="pl-list-wrap")
            yield Button(f"{design.icon('ai.done')} 运行所选流水线", id="pl-run",
                         variant="primary")
            yield Static(f"{design.icon('status.hint')} 自定义 YAML "
                         f"{design.icon('misc.caret_right')}", id="pl-adv-head")
            with Vertical(id="pl-yaml-box") as yaml_box:
                yaml_box.display = False
                yield TextArea(id="pl-yaml")
                yield Button(f"{design.icon('task.success')} 保存模板",
                             id="pl-save", variant="default")
        yield Static("", id="pl-result")

    def on_mount(self) -> None:
        self.set_interval(STEPS_REFRESH_S, self._auto_reload_steps)
        self.run_worker(self.refresh_pipelines(), exclusive=True)

    # ---- 模板卡 ----
    async def refresh_pipelines(self) -> None:
        try:
            data = await self.client.list_pipelines()
        except Exception as exc:
            self.query_one("#pl-result", Static).update(f"[$nova]模板加载失败[/] {exc}")
            return
        self._pipelines = (data or {}).get("items", [])
        option_list = OptionList(*[
            Option(
                f"{design.icon('nav.pipeline' if p.get('is_builtin') else 'misc.star_rank_1')}"
                f" {p.get('title', p.get('name', '?'))}"
                f"  [dim]{p.get('name')} · {p.get('description', '')}"
                f" · {len(p.get('steps', []))} 步[/dim]",
                id=p.get("name"),
            ) for p in self._pipelines
        ], id="pl-list")
        wrap = self.query_one("#pl-list-wrap", Static)
        await wrap.mount(option_list)
        wrap.update("")

    def _selected_name(self) -> str | None:
        try:
            option_list = self.query_one("#pl-list", OptionList)
        except Exception:
            return None
        if option_list.option_count == 0 or option_list.highlighted is None:
            return None
        return option_list.get_option_at_index(option_list.highlighted).id

    # ---- 折叠区 ----
    def on_static_click(self, event: Static.Click) -> None:
        if event.static.id == "pl-adv-head":
            box = self.query_one("#pl-yaml-box", Vertical)
            box.display = not box.display
            caret = design.icon("misc.caret_down" if box.display else "misc.caret_right")
            event.static.update(
                f"{design.icon('status.hint')} 自定义 YAML {caret}")

    # ---- 运行与时间线 ----
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        result = self.query_one("#pl-result", Static)
        if event.button.id == "pl-run":
            name = self._selected_name()
            if not name:
                result.update(
                    f"[${'nova'}]{design.icon('status.error')} 请先选择流水线模板[/]")
                return
            try:
                data = await self.client.run_pipeline(name)
            except Exception as exc:
                result.update(f"[${'nova'}]运行失败[/] {exc}")
                return
            self._task_uuid = str(data["task_uuid"])
            result.update(
                f"[${'aurora'}]{design.icon('task.success')} 流水线已启动[/] "
                f"{self._task_uuid[:8]}，失败步骤可在时间线上单独重试。")
            await self._mount_run_view()
        elif event.button.id == "pl-save":
            yaml_text = self.query_one("#pl-yaml", TextArea).text
            try:
                data = await self.client.save_pipeline(yaml_text)
            except Exception as exc:
                result.update(f"[${'nova'}]保存失败[/] {exc}")
                return
            result.update(
                f"[${'aurora'}]{design.icon('task.success')} 模板已保存[/]"
                f" {data.get('name', '')}（已落 PostgreSQL）")
            await self.refresh_pipelines()

    async def _mount_run_view(self) -> None:
        """运行视图：任务进度卡 + 步骤时间线，随后按任务详情填 steps。"""
        for old in self.query(TaskProgressCard):
            await old.remove()
        for old in self.query(StepTimeline):
            await old.remove()
        if not self._task_uuid:
            return
        card = TaskProgressCard(self.client, self._task_uuid, "pipeline")
        timeline = StepTimeline(self.client, self._task_uuid, [], title="运行时间线")
        await self.mount(card)
        await self.mount(timeline)
        self._active = True
        await self._reload_steps()

    async def _reload_steps(self) -> None:
        """拉取任务详情刷新时间线（status/progress 变化与续跑后共用）。"""
        if not self._task_uuid:
            return
        try:
            detail = await self.client.task_detail(self._task_uuid)
        except Exception:
            return
        try:
            timeline = self.query_one(StepTimeline)
        except Exception:
            return
        await timeline.set_steps(list(detail.get("steps", [])))

    def on_task_progress_card_finished(self, event: TaskProgressCard.Finished) -> None:
        """进度卡到达终态：终局重拉一次 steps（终态步骤着色）。"""
        self._active = False
        self.run_worker(self._reload_steps(), exclusive=True)

    def on_step_timeline_step_retried(self, event: StepTimeline.StepRetried) -> None:
        """失败步骤已请求续跑：续跑原地更新同一任务，刷新时间线。"""
        self.query_one("#pl-result", Static).update(
            f"[${'aurora'}]{design.icon('task.running')} 已请求从步骤 "
            f"{event.step_index + 1} 续跑[/]（前序产物已保留）· {event.task_uuid[:8]}")
        self.run_worker(self._reload_steps(), exclusive=True)
