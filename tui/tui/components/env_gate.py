# -*- coding: utf-8 -*-
"""表单页环境门禁（方案 §2.4 降级纪律 / L9②）：env-check 缺失 → 表单禁用 + 缺失卡。

依赖清单以插件注册表 env_dep（env-check 项名子串匹配，侧栏健康点同源）为唯一
事实源；缺失时页面禁用 GATE_DISABLE 选择器命中的控件并挂缺失卡（molten 描边
+ 告警 wash 底，静态——终端红线禁呼吸动画），env_items 修复后自动解禁撤卡。
用法：页面混入 EnvGateMixin，声明 GATE_DISABLE 选择器元组，on_mount 里
`self.set_interval(GATE_INTERVAL_S, self.apply_env_gate)` + 立即调用一次；
页面须持有 `self._app`（app 引用）且 id 为 `page-<key>`（反查插件 env_dep）。
"""
from __future__ import annotations

from textual.widgets import Static

from tui.theme.generated import tokens as design

GATE_INTERVAL_S = 5.0  # 与 app 健康循环同频（env_items 更新即随动）


class EnvMissingCard(Static):
    """环境依赖缺失卡（molten 描边 + alertWashBg 静态 wash）。"""

    DEFAULT_CSS = """
    EnvMissingCard { display: none; border: round $molten; background: $alertWashBg;
        color: $ink-900; padding: 0 1; margin-top: 1; }
    EnvMissingCard.env-missing-on { display: block; }
    """


def missing_deps(env_items: list[dict], wanted: tuple[str, ...]) -> list[dict]:
    """env_dep 子串匹配 → 未就绪依赖项 [{name, detail}]。

    wanted 空 = 页面无模块级依赖（恒放行）；env_items 空 = 体检未到达
    （不误禁用——服务不可达由连接面板/首页错误态负责，门禁不越权）。
    """
    if not wanted or not env_items:
        return []
    matched = [item for item in env_items
               if any(w in str(item.get("name", "")) for w in wanted)]
    return [item for item in matched if not item.get("ok")]


def missing_card_text(missing: list[dict]) -> str:
    """缺失卡文案：项名 + detail 原文（保留服务端修复指引）。"""
    lines = [
        f"[${'molten'}]{design.icon('status.warn')} 环境依赖缺失[/]"
        f"（{len(missing)} 项）——表单已禁用，修复后自动恢复：",
    ]
    for item in missing:
        lines.append(
            f"  [${'nova'}]{design.icon('status.error')}[/] "
            f"{item.get('name', '?')}：[dim]{item.get('detail', '')}[/dim]")
    return "\n".join(lines)


class EnvGateMixin:
    """页面环境门禁混入（非 Widget，随页面类多继承）。

    用法：`self.set_interval(GATE_INTERVAL_S, self.apply_env_gate)`（异步回调，
    Textual 定时器原生支持）+ on_mount 里 `self.call_later(self.apply_env_gate)`
    首查。
    """

    GATE_DISABLE: tuple[str, ...] = ()  # 缺失时置 disabled 的控件选择器

    async def apply_env_gate(self) -> None:
        """缺失 → 禁用 GATE_DISABLE 控件 + 显示缺失卡；恢复 → 解禁撤卡。"""
        app = getattr(self, "_app", None)
        if app is None:
            return
        wanted: tuple[str, ...] = ()
        try:
            plugin = next(p for p in app.pages if f"page-{p.key}" == self.id)
        except StopIteration:
            plugin = None
        if plugin is not None:
            wanted = plugin.env_dep
        missing = missing_deps(list(app.env_items), wanted)
        for selector in self.GATE_DISABLE:
            for node in self.query(selector):
                node.disabled = bool(missing)
        await self._sync_gate_card(missing)

    async def _sync_gate_card(self, missing: list[dict]) -> None:
        """缺失卡增删改（挂页面顶部；页面卸载竞态静默）。"""
        try:
            card = self.query_one(EnvMissingCard)
        except Exception:
            card = None
        if not missing:
            if card is not None:
                card.remove_class("env-missing-on")
            return
        text = missing_card_text(missing)
        if card is not None:
            card.update(text)
            card.add_class("env-missing-on")
            return
        card = EnvMissingCard(text, classes="env-missing-card env-missing-on")
        anchor = self.children[0] if self.children else None
        try:
            if anchor is not None:
                await self.mount(card, before=anchor)
            else:
                await self.mount(card)
        except Exception:
            pass  # 页面已被换装移除等竞态
