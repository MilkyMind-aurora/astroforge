# -*- coding: utf-8 -*-
"""设置页（方案 §3.5 分组卡，MF2 外观组落地）。

分组：「外观」（主题 OptionList：deep-space/dawn，选择即 `app.theme` 热切
（Textual refresh_css 瞬时生效，§1.5）+ 持久化经 app_settings appearance.theme
——服务端白名单 V1-B.6；数据库不可达时如实提示「本次会话生效」）、「星仔」
（开关+台词库预览，quotes.yaml 数据源）、「服务」（内存阈值+爬虫间隔，继承）
、「路径」（config-summary 摘要，继承）+ token 重置。
"""
from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Button, Input, OptionList, Static, Switch
from textual.widgets.option_list import Option

from tui.service_client import ServiceClient
from tui.theme.generated import tokens as design
from tui.ui.mascot import QUOTES

EDITABLE = {
    "memory_warning_gb": "内存黄色预警 (GB)",
    "memory_critical_gb": "内存红色告警 (GB)",
    "request_interval": "爬虫请求间隔 (秒)",
    "default_template": "默认 DOCX 模板",
}


def quote_preview(event: str = "boot", limit: int = 3) -> str:
    """台词库预览行（quotes.yaml 经 mascot.QUOTES 兼容层；纯函数，单测覆盖）。"""
    lines = QUOTES.get(event) or []
    return " ｜ ".join(lines[:limit]) or "（台词库为空）"


class SettingsPage(VerticalScroll):
    """设置页：外观组（主题热切+持久化）/ 星仔 / 服务阈值 / 摘要。"""

    CSS = """
    #settings-body { color: $ink-900; margin-top: 1; }
    .settings-group { border: round $border-subtle; background: $card;
        padding: 0 2; margin-top: 1; }
    .settings-group-title { color: $ink-600; padding-top: 1; }
    #st-theme { height: auto; max-height: 5; border: round $border-subtle;
        background: $sunken; }
    #st-mascot-preview { color: $ink-400; }
    #st-summary { color: $ink-600; }
    """

    def __init__(self, client: ServiceClient, app_ref=None) -> None:  # noqa: ANN001
        super().__init__(id="page-settings")
        self.client = client
        self._app = app_ref
        self._loaded = False

    def compose(self) -> ComposeResult:
        yield Static(f"[b]{design.icon('nav.settings')} 设置[/b]  正在加载…",
                     id="settings-body")

    def on_mount(self) -> None:
        self.run_worker(self.refresh_settings(), exclusive=True)

    async def refresh_settings(self) -> None:
        try:
            summary = (await self.client.config_summary()) or {}
            overrides = ((await self.client.list_app_settings()) or {}).get("items", {})
        except Exception as exc:
            await self.mount(Static(f"[${'nova'}]加载失败[/] {exc}", id="settings-err"))
            return

        box = Vertical(id="settings-box", classes="settings-root")
        await self.mount(box)

        # ---- 外观组（主题热切 + app_settings 持久化）----
        with Vertical(classes="settings-group") as appearance:
            await box.mount(appearance)
            await appearance.mount(Static("[b]外观[/b]  （选择即热切，重启后保持）",
                                          classes="settings-group-title"))
            saved = str((overrides.get("appearance.theme") or {}).get("value", "")
                        ).strip()
            current = saved if saved in design.THEMES else design.DEFAULT_THEME
            def _theme_check(name: str) -> str:
                check = f"[${'aurora'}]{design.icon('task.success')}[/$aurora] "
                return check if name == current else "  "

            option_list = OptionList(*[
                Option(
                    f"{_theme_check(name)}{name}  "
                    f"[dim]{'夜 · 默认' if name == design.DEFAULT_THEME else '昼'}[/dim]",
                    id=name,
                ) for name in design.THEMES
            ], id="st-theme")
            await appearance.mount(option_list)
            await appearance.mount(Static(
                f"星仔台词库预览：{quote_preview('boot')}", id="st-mascot-preview"))
            mascot_switch = Switch(
                value=bool((overrides.get("appearance.mascot") or {})
                           .get("value", True)), id="st-mascot")
            await appearance.mount(mascot_switch)
            await appearance.mount(Static("星仔台词气泡（appearance.mascot）"))

        # ---- 星仔开关文案 + 服务组 ----
        with Vertical(classes="settings-group") as service:
            await box.mount(service)
            await service.mount(Static("[b]服务[/b]  （覆盖设置保存到 app_settings）",
                                       classes="settings-group-title"))
            monitor = summary.get("monitor", {})
            for key, label in EDITABLE.items():
                current_value = (overrides.get(key) or {}).get(
                    "value", monitor.get(key, ""))
                await service.mount(Input(value=str(current_value),
                                          placeholder=label, id=f"in-{key}"))
            await service.mount(Button("保存覆盖设置", id="btn-save", variant="primary"))
            await service.mount(Button("重置服务 Token（旧 token 立即失效）",
                                       id="btn-token", variant="warning"))
            await service.mount(Static("", id="st-summary"))

        self._render_summary(summary)
        if not self._loaded:
            self._loaded = True
        self.query_one("#settings-body", Static).display = False

    def _render_summary(self, summary: dict) -> None:
        monitor = summary.get("monitor", {})
        appearance = summary.get("appearance", {})
        lines = [
            f"服务: {summary.get('service', {})}",
            f"数据库: {summary.get('database', {})}",
            f"AI: {summary.get('ai', {})}",
            f"监控: 内存预警 {monitor.get('memory_warning_gb')}GB / "
            f"红线 {monitor.get('memory_critical_gb')}GB",
            f"外观: 主题 {appearance.get('theme', '-')} · "
            f"星野 {'开' if appearance.get('starfield') else '关'}",
        ]
        try:
            self.query_one("#st-summary", Static).update("\n".join(lines))
        except Exception:
            pass

    # ---- 主题热切（refresh_css 瞬时生效）----
    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_list.id != "st-theme" or self._app is None:
            return
        name = str(event.option_id)
        self._app.action_set_theme(name)
        try:
            await self.client.set_app_setting("appearance.theme", name)
        except Exception as exc:
            self.app.notify(f"主题已热切，但持久化失败（数据库不可用）：{exc}",
                            severity="warning")
        else:
            self.app.notify("主题选择已保存（重启后保持）", severity="information")

    async def on_switch_changed(self, event: Switch.Changed) -> None:
        if event.switch.id != "st-mascot":
            return
        try:
            await self.client.set_app_setting("appearance.mascot", bool(event.value))
        except Exception as exc:
            self.app.notify(f"星仔开关保存失败：{exc}", severity="warning")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-save":
            payload = {}
            for key in EDITABLE:
                raw = self.query_one(f"#in-{key}", Input).value.strip()
                if raw == "":
                    continue
                payload[key] = raw if key in {"default_template"} else float(raw)
            try:
                for key, val in payload.items():
                    await self.client.set_app_setting(key, val)
                self.app.notify("覆盖设置已保存", severity="information")
            except Exception as exc:
                self.app.notify(f"保存失败: {exc}", severity="error")
        elif event.button.id == "btn-token":
            try:
                await self.client.reset_token()
                # 重置后重新读取 token 文件
                self.client.__init__()
                self.app.notify("Token 已重置并重新读取", severity="warning")
            except Exception as exc:
                self.app.notify(f"重置失败: {exc}", severity="error")
