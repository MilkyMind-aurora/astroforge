# -*- coding: utf-8 -*-
"""终端内文件浏览器（方案 1.5，数据源 /files/browse 白名单目录）。"""
from __future__ import annotations

from pathlib import Path

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option

from tui.service_client import ServiceClient


class FileBrowserScreen(ModalScreen):
    """双区浏览器：上列表（目录/文件，OptionList 键盘可选）、下预览（文本 ≤5MB）。"""

    CSS = """
    FileBrowserScreen { align: center middle; }
    #fb-box { width: 90%; height: 80%; border: round #8B7CF6; padding: 1 2; background: $surface; }
    #fb-list { height: 2fr; border: solid $primary-muted; margin-bottom: 1; }
    #fb-preview { height: 1fr; border: solid $primary-muted; padding: 0 1; overflow: auto; }
    #fb-path { margin-bottom: 1; }
    """

    def __init__(self, client: ServiceClient) -> None:
        super().__init__()
        self.client = client
        self._entries: list[tuple[str, str | None, bool]] = []  # (label, path, is_dir)

    def compose(self) -> ComposeResult:
        with Vertical(id="fb-box"):
            yield Static("📂 /", id="fb-path")
            yield OptionList(id="fb-list")
            yield Static("（↑↓ 选择，回车进入目录/预览文件）", id="fb-preview")
            yield Button("关闭 (Esc)", id="fb-close", variant="default")

    def on_mount(self) -> None:
        self.run_worker(self.load(""), exclusive=True)

    async def load(self, path: str) -> None:
        try:
            data = await self.client.browse_files(path)
        except Exception as exc:
            self.query_one("#fb-preview", Static).update(f"[red]浏览失败[/red] {exc}")
            return
        self.current = data.get("path", path)
        self.query_one("#fb-path", Static).update(f"📂 {self.current}")
        option_list = self.query_one("#fb-list", OptionList)
        option_list.clear_options()
        # 首项恒为返回上级
        parent = str(Path(self.current).parent)
        option_list.add_option(Option("📁 [..] 上一级", id=parent))
        self._entries = [(parent, True)]
        for d in data.get("dirs", []):
            option_list.add_option(Option(f"📁 {d['name']}", id=d["path"]))
            self._entries.append((d["path"], True))
        for f in data.get("files", []):
            size_kb = f["size_bytes"] / 1024
            option_list.add_option(Option(f"📄 {f['name']}  {size_kb:.1f}KB", id=f["path"]))
            self._entries.append((f["path"], False))
        if option_list.option_count == 0:
            option_list.add_option(Option("（空目录）", id=""))

    async def open_preview(self, path: str) -> None:
        try:
            data = await self.client.preview_file(path)
            content = (data.get("content") or "")[:2000]
            suffix = data.get("suffix", "")
            self.query_one("#fb-preview", Static).update(
                f"[bold]{path}[/bold] [dim]({suffix}，前 2000 字符）[/dim]\n\n{content}"
            )
        except Exception as exc:
            self.query_one("#fb-preview", Static).update(f"[red]预览失败[/red] {exc}")

    async def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        option_id = event.option.id
        if not option_id:
            return
        is_dir = any(p == option_id and d for p, d in self._entries)
        if is_dir:
            self.run_worker(self.load(option_id), exclusive=True)
        else:
            self.run_worker(self.open_preview(option_id), exclusive=True)

    def on_key(self, event) -> None:  # noqa: ANN001
        if event.key == "escape":
            self.dismiss()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "fb-close":
            self.dismiss()
