# -*- coding: utf-8 -*-
"""筛选 chips 胶囊组（方案 §1.8 #7 组件规格 / §3.5 状态筛选 / L17 统一胶囊族）。

selected=aurora 实底 + onAurora 深字（L17 统一裁定；tokens 硬规则「aurora 底
一律深字，禁白字」）；未选=container 底 + ink-600。TUI 无共享指示层，不做液态
滑移（#3 属 Flutter 监控页），选中态切换走 T_PRESS 档内的瞬时反馈。
ChipAction 为同族动作胶囊（快捷入口等无选中态的动作位），形态与 ChipBar 统一。
"""
from __future__ import annotations

from textual.containers import Horizontal
from textual.message import Message
from textual.widgets import Button


class ChipBar(Horizontal):
    """横向 chips：选项 [(value, label)]，默认选中第一项；点击切换选中。"""

    DEFAULT_CSS = """
    ChipBar { height: auto; }
    ChipBar .chip { min-width: 8; height: 3; margin-right: 1; border: none;
        background: $container; color: $ink-600; text-align: center; }
    ChipBar .chip:hover { background: $containerPressed; color: $ink-900; }
    ChipBar .chip.selected { background: $aurora; color: $onAurora;
        text-style: bold; }
    """

    class Changed(Message):
        """选中项变化（value 为选项值）。"""

        def __init__(self, chip_bar: "ChipBar", value: str | None) -> None:
            super().__init__()
            self.chip_bar = chip_bar
            self.value = value

    def __init__(self, options: list[tuple[str | None, str]], id: str | None = None) -> None:
        super().__init__(id=id)
        self._options = list(options)
        self._selected: str | None = self._options[0][0] if self._options else None

    def compose(self):
        for index, (value, label) in enumerate(self._options):
            button = Button(label, id=f"chip-{index}", classes="chip")
            button.set_class(value == self._selected, "selected")
            yield button

    @property
    def selected(self) -> str | None:
        return self._selected

    def on_button_pressed(self, event: Button.Pressed) -> None:
        index = int((event.button.id or "chip-0").rsplit("-", 1)[1])
        value = self._options[index][0]
        if value == self._selected:
            return
        self._selected = value
        for i, button in enumerate(self.query(Button)):
            button.set_class(self._options[i][0] == value, "selected")
        self.post_message(self.Changed(self, value))


class ChipAction(Button):
    """胶囊动作 chip（首页快捷入口等动作位）：无选中态，胶囊形态与 ChipBar 统一。"""

    DEFAULT_CSS = """
    ChipAction { min-width: 8; height: 3; margin-right: 1; border: none;
        background: $container; color: $ink-600; text-align: center; }
    ChipAction:hover { background: $containerPressed; color: $ink-900; }
    ChipAction:focus { background: $containerPressed; color: $ink-900; }
    """
