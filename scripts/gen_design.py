# -*- coding: utf-8 -*-
"""设计契约渲染器：config/design/*.yaml → 三端产物（方案 §2.3 / V1-B.2 / §1.5）。

源（唯一事实源——三端禁止在其外硬编码色值与星符，CI grep 断言）：
  config/design/tokens.yaml    色板/圆角/间距/字阶/动效/交互参数
  config/design/icons.yaml     星符语义映射
  config/design/quotes.yaml    星仔台词库（本脚本校验：单条 ≤24 字等）
  config/design/themes/*/      主题包：点分键覆盖根 tokens（合并语义同 server
                               config_loader 的 platform_overrides——点分键覆盖、
                               未覆盖键回落全局）

产物（全部确定性输出：同输入必同字节，幂等即 CI 门禁 V1-B.5）：
  tui/tui/theme/generated/tokens.tcss   Textual 工具类样式（默认主题 deep-space）
  tui/tui/theme/generated/tokens.py     Python 常量 + css_variables() + 星符表
  app/lib/core/design/tokens.g.dart     AstroPalette / lerpPalette / AstroTheme 工厂
                                        （替代 app/lib/core/theme.dart，禁 fromSeed）
  modules/_shared/star_console.py       顶部「星空设计 token」生成段（渲染器四件套
                                        是 V1-B.4/MF3 的活，本脚本只管样式段）
  config/design/starfield/seed.json     星野种子（60~90 颗确定性坐标，三端同源）

用法：
  python scripts/gen_design.py             # 全量生成（星野用默认种子）
  python scripts/gen_design.py --seed 42   # 以指定种子重生成星野坐标

退出码：0=成功；2=设计源校验失败（先修 yaml 再谈生成）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_THEME = "deep-space"        # §2.2：deep-space 为内置夜主题（默认）
DEFAULT_STAR_SEED = 20260925        # 提交进仓库的星野种子（确定性基线）
QUOTE_MAX_CHARS = 24                # 星仔台词单条上限（星仔规格 §六 CI 断言）
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# 生成物相对路径（generate_all / ui_doctor gen-idempotent / 单测三方共用）
ARTIFACT_TCSS = "tui/tui/theme/generated/tokens.tcss"
ARTIFACT_TPY = "tui/tui/theme/generated/tokens.py"
ARTIFACT_DART = "app/lib/core/design/tokens.g.dart"
ARTIFACT_CLI = "modules/_shared/star_console.py"
ARTIFACT_SEED = "config/design/starfield/seed.json"
ARTIFACTS = (ARTIFACT_TCSS, ARTIFACT_TPY, ARTIFACT_DART, ARTIFACT_CLI, ARTIFACT_SEED)

STAR_CONSOLE_BEGIN = "# ==== BEGIN 星空设计 token（scripts/gen_design.py 生成，禁手改）===="
STAR_CONSOLE_END = "# ==== END 星空设计 token ===="
STAR_CONSOLE_PREAMBLE = '''# -*- coding: utf-8 -*-
"""CLI 星幕渲染器（方案 §2.5 / §四）。

顶部「星空设计 token」段由 scripts/gen_design.py 生成（禁手改）；渲染器四件套
（banner/stage/progress/result_card/error_card/log）于 V1-B.4/MF3 落地，届时
颜色与星符一律取自生成段（运行时也可直读 config/design/tokens.yaml）。
降级纪律【硬性】：非 TTY 或 rich 不可导入 → 全部回退纯文本；stdout 日志行
（``[INFO] ``/``[ERROR] `` 前缀）与结果 JSON 契约字节不变（服务核心逐行捕获零改动）。
"""
from __future__ import annotations

'''
STAR_CONSOLE_TAIL = '''


def palette(mode: str = "dark") -> dict[str, str]:
    """指定档 token 表（MF3 渲染器与降级路径共用的取色入口；值一律来自生成段）。"""
    try:
        return dict(STAR_TOKENS[mode])
    except KeyError:
        raise ValueError(f"未知色彩档: {mode}（可选: dark/light）") from None
'''

# 生成物必须存在的 token 键（缺键=契约破坏，gen 直接报错而非产出残缺三端）
REQUIRED_COLOR_TOKENS = (
    "bg", "sunken", "card", "container", "cardRaised", "containerPressed", "faint",
    "ink-900", "ink-600", "ink-400", "stroke", "strokeFocus",
    "aurora", "auroraText", "nebula", "nebulaText", "hydrogen",
    "molten", "moltenText", "nova",
    "onAurora", "onNebula", "onHydrogen", "onMolten", "onNova",
    "chipsSelectedBg", "aiContainerBg", "errorWashBg", "runningWashBg", "alertWashBg",
)


# ============================================================
# 载入与合并（点分键覆盖，语义同 server config_loader.platform_overrides）
# ============================================================

def set_dotted(data: dict[str, Any], dotted: str, value: Any) -> None:
    """把 "a.b.c" 点分键写入嵌套 dict（与 config_loader._set_dotted 同语义）。"""
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise ValueError(f"主题覆盖键冲突: {dotted}（{part} 已是标量）")
    node[parts[-1]] = value


def flatten_dotted(mapping: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """嵌套 dict → 点分键叶值表（主题包既可用嵌套 YAML 也可用点分键，二者等价）。"""
    out: dict[str, Any] = {}
    for key, value in mapping.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            out.update(flatten_dotted(value, path))
        else:
            out[path] = value
    return out


def merge_theme(root_tokens: dict[str, Any], theme_raw: dict[str, Any]) -> dict[str, Any]:
    """主题包覆盖合并：theme 的（扁平化后）点分键覆盖根 tokens，未覆盖键回落。"""
    merged = deepcopy(root_tokens)
    for dotted, value in flatten_dotted(theme_raw).items():
        set_dotted(merged, dotted, deepcopy(value))
    return merged


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} 顶层必须是映射，实际是 {type(data).__name__}")
    return data


def load_bundle(repo_root: Path) -> dict[str, Any]:
    """读取 design 资产：tokens + icons + quotes + themes/*（含 banner 等伴生文件忽略）。"""
    design_dir = repo_root / "config" / "design"
    bundle: dict[str, Any] = {
        "tokens": _load_yaml(design_dir / "tokens.yaml"),
        "icons": _load_yaml(design_dir / "icons.yaml"),
        "quotes": _load_yaml(design_dir / "quotes.yaml"),
        "themes": {},
    }
    themes_dir = design_dir / "themes"
    if themes_dir.is_dir():
        for tdir in sorted(themes_dir.iterdir()):
            tfile = tdir / "tokens.yaml"
            if tdir.is_dir() and tfile.exists():
                bundle["themes"][tdir.name] = _load_yaml(tfile)
    return bundle


# ============================================================
# 校验（yaml 是唯一事实源，坏源在生成前拦下）
# ============================================================

def _validate_colors(color: dict[str, Any], where: str, errors: list[str]) -> None:
    for name in REQUIRED_COLOR_TOKENS:
        if name not in color:
            errors.append(f"{where}: 缺色 token color.{name}")
            continue
        value = color[name]
        if isinstance(value, dict):
            for mode in ("light", "dark"):
                v = value.get(mode)
                if not isinstance(v, str) or not HEX_RE.match(v):
                    errors.append(f"{where}: color.{name}.{mode} 非合法 #RRGGBB：{v!r}")
        elif isinstance(value, str):
            if not HEX_RE.match(value):
                errors.append(f"{where}: color.{name} 非合法 #RRGGBB：{value!r}")
        else:
            errors.append(f"{where}: color.{name} 既非双档映射也非 hex 字符串：{value!r}")


def validate_bundle(bundle: dict[str, Any]) -> None:
    """设计源校验：色值格式/必需键/星野密度/台词长度与结构/主题模式合法性。"""
    errors: list[str] = []
    tokens = bundle["tokens"]

    color = tokens.get("color") or {}
    _validate_colors(color, "tokens.yaml", errors)

    galaxy = color.get("galaxy") or {}
    for key in ("stops", "stopsLight", "positions"):
        if not isinstance(galaxy.get(key), list) or len(galaxy[key]) != 3:
            errors.append(f"tokens.yaml: color.galaxy.{key} 必须是长度 3 的列表")
    for key in ("stops", "stopsLight"):
        for v in galaxy.get(key) or []:
            if not isinstance(v, str) or not HEX_RE.match(v):
                errors.append(f"tokens.yaml: color.galaxy.{key} 含非法色值 {v!r}")

    starfield = color.get("starfield") or {}
    density = starfield.get("density")
    if (
        not isinstance(density, list)
        or len(density) != 2
        or not all(isinstance(v, int) for v in density)
        or not (0 < density[0] <= density[1] <= 10_000)
    ):
        errors.append(f"tokens.yaml: color.starfield.density 必须是 [min, max] 整数对：{density!r}")

    for section, keys in (
        ("radius", ("pill", "lg", "md", "sm")),
        ("space", ("window", "card", "gap", "gap-lg", "section", "section-lg", "empty")),
        ("type", ("display", "h1", "h2", "title", "title-sm", "body", "body-sm",
                  "caption", "label", "kpi", "mono_family")),
    ):
        missing = [k for k in keys if k not in (tokens.get(section) or {})]
        if missing:
            errors.append(f"tokens.yaml: 缺 {section}.{'/'.join(missing)}")

    motion = tokens.get("motion") or {}
    for path in ("flutter.spring_press", "flutter.spring_soft", "flutter.spring_pop",
                 "flutter.tween_color", "flutter.tween_move", "flutter.tween_theme"):
        node: Any = motion
        for part in path.split("."):
            node = (node or {}).get(part) if isinstance(node, dict) else None
        if not isinstance(node, dict):
            errors.append(f"tokens.yaml: 缺 motion.{path}")

    tui = tokens.get("tui") or {}
    border_levels = tui.get("border_levels") or {}
    for level in ("subtle", "normal", "active"):
        token_name = border_levels.get(level)
        if not isinstance(token_name, str) or token_name not in REQUIRED_COLOR_TOKENS:
            errors.append(f"tokens.yaml: tui.border_levels.{level} 必须指向色 token：{token_name!r}")
    if not isinstance(tui.get("thinking_opacity"), (int, float)):
        errors.append("tokens.yaml: 缺 tui.thinking_opacity")

    # 星仔台词库：单条 ≤24 字（含标点）、事件组非空、dispatch 引用的事件必须存在
    quotes = bundle["quotes"]
    events = quotes.get("events") or {}
    if not events:
        errors.append("quotes.yaml: events 为空")
    for event, body in events.items():
        lines = (body or {}).get("lines")
        if not isinstance(lines, list) or not lines:
            errors.append(f"quotes.yaml: events.{event}.lines 为空")
            continue
        for line in lines:
            if not isinstance(line, str):
                errors.append(f"quotes.yaml: events.{event} 台词非字符串：{line!r}")
            elif len(line) > QUOTE_MAX_CHARS:
                errors.append(
                    f"quotes.yaml: events.{event} 台词超 {QUOTE_MAX_CHARS} 字（{len(line)}）：{line}"
                )
    dispatch = quotes.get("dispatch") or {}
    for event in dispatch:
        if event != "global" and event not in events:
            errors.append(f"quotes.yaml: dispatch.{event} 引用了不存在的事件组")

    # 主题包：模式合法；点分键覆盖冲突在 merge_theme 时抛错
    for name, raw in bundle["themes"].items():
        mode = (raw.get("meta") or {}).get("mode")
        if mode not in ("light", "dark"):
            errors.append(f"themes/{name}/tokens.yaml: meta.mode 必须是 light|dark，实际 {mode!r}")
        try:
            merge_theme(tokens, raw)
        except ValueError as exc:
            errors.append(f"themes/{name}: {exc}")

    if errors:
        for line in errors:
            print(f"[gen_design] 校验失败: {line}", file=sys.stderr)
        raise DesignValidationError(f"设计源校验失败 {len(errors)} 项（先修 yaml 再生成）")


class DesignValidationError(RuntimeError):
    """设计源不合法（yaml 层面），生成器拒绝产出三端产物。"""


# ============================================================
# 解析：调色板 / 主题视图 / 星野种子
# ============================================================

def palette_of(color: dict[str, Any], mode: str) -> dict[str, str]:
    """按档（light/dark）解析色板：双档映射取档值；标量覆盖则双档同值。"""
    out: dict[str, str] = {}
    for name, value in color.items():
        if name in ("galaxy", "starfield"):
            continue  # 非单色 token，单独导出
        if isinstance(value, dict):
            if mode not in value:
                raise DesignValidationError(f"color.{name} 缺 {mode} 档")
            out[name] = value[mode]
        else:
            out[name] = value
    return out


def theme_palette(root_tokens: dict[str, Any], theme_raw: dict[str, Any]) -> dict[str, str]:
    """主题包解析值：点分键覆盖合并后，按该主题 meta.mode 取档。"""
    merged = merge_theme(root_tokens, theme_raw)
    mode = (theme_raw.get("meta") or {}).get("mode") or "dark"
    return palette_of(merged.get("color") or {}, mode)


def flatten_icons(icons: dict[str, Any]) -> dict[str, str]:
    """icons.yaml → 点分键星符表（nav.home → ✦）。"""
    flat = flatten_dotted(icons)
    out: dict[str, str] = {}
    for path, glyph in flat.items():
        if path == "version":
            continue
        if not isinstance(glyph, str) or not glyph:
            raise DesignValidationError(f"icons.yaml: {path} 星符为空")
        out[path] = glyph
    return out


def render_starfield(seed: int, density: list[int]) -> dict[str, Any]:
    """星野种子：60~90 颗（density 决定）确定性坐标；同 seed 必同输出（三端同源）。

    注：这里刻意用可复现的 random.Random（布局生成，非加密用途）——
    幂等门禁要求同输入必同字节，secrets 这类不可复现随机源反而破坏契约。
    """
    lo, hi = density
    rng = random.Random(seed)
    stars = [
        {
            "x": round(rng.random(), 4),                       # 归一化坐标 0..1
            "y": round(rng.random(), 4),
            "tier": rng.choices((0, 1, 2), weights=(55, 30, 15))[0],  # 暗星多亮星少
            "phase": round(rng.random() * 4.0, 3),             # 4s 漂移周期内的相位
        }
        for _ in range(rng.randint(lo, hi))
    ]
    return {
        "version": 1,
        "generator": "scripts/gen_design.py",
        "seed": seed,
        "density": [lo, hi],
        "count": len(stars),
        "stars": stars,
    }


# ============================================================
# 渲染：TUI（tokens.tcss / tokens.py）
# ============================================================

TCSS_TEXT_TOKENS = ("ink-900", "ink-600", "ink-400", "aurora", "auroraText", "nebula",
                    "nebulaText", "hydrogen", "molten", "moltenText", "nova")
TCSS_SURFACE_TOKENS = ("bg", "sunken", "card", "container", "cardRaised",
                       "containerPressed", "chipsSelectedBg", "aiContainerBg",
                       "errorWashBg", "runningWashBg", "alertWashBg")


def _py(value: Any) -> str:
    """Python 字面量：字符串统一双引号（utf-8 直出星符），bool 按Python 拼写。"""
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool) or value is None or isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_py(v) for v in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_py(k)}: {_py(v)}" for k, v in value.items()) + "}"
    return repr(value)


LINE_LIMIT = 96  # 单行字面量软上限（产物须过 ruff 110 列，留缩进余量）


def _py_lines(value: Any, indent: int) -> list[str]:
    """嵌套字面量分行渲染：能单行放下（≤LINE_LIMIT 列）保持单行，否则递归展开。"""
    pad = " " * indent
    single = _py(value)
    if len(single) + indent <= LINE_LIMIT or not isinstance(value, (dict, list, tuple)):
        return [single]
    open_ch, close_ch = ("{", "}") if isinstance(value, dict) else ("[", "]")
    rows = [open_ch]
    items = value.items() if isinstance(value, dict) else value
    for key, item in (
        items if isinstance(value, dict) else [(None, item) for item in items]
    ):
        inner = _py_lines(item, indent + 4)
        prefix = f"{pad}{_py(key)}: " if key is not None else f"{pad}"
        if len(inner) == 1:
            rows.append(f"{prefix}{inner[0]},")
        else:
            rows.append(f"{prefix}{inner[0]}")
            rows.extend(inner[1:])
            rows[-1] += ","
    rows.append(pad[:-4] + close_ch)
    return rows


def render_tui_tcss(palette: dict[str, str], border_levels: dict[str, str], sha: str) -> str:
    """Textual 工具类样式：默认主题（deep-space 夜）字面色 + 语义类名。"""
    lines = [
        "/* ============================================================",
        " * AstroForge TUI token 样式（生成物 —— scripts/gen_design.py，禁手改）",
        f" * 源：config/design/tokens.yaml（sha256:{sha}）",
        f" * 默认主题：{DEFAULT_THEME}（夜）；类名 = 前缀 + token 名（.c-ink-900/.bg-card）。",
        " * 主题热切走 tokens.py css_variables() + refresh_css（§1.5），本文件是默认档。",
        " * ============================================================ */",
        "",
        "/* 文字（ink 阶梯 + 强调色文本位；夜档强调色文本图形双用） */",
    ]
    lines += [f".c-{name} {{ color: {palette[name]}; }}" for name in TCSS_TEXT_TOKENS]
    lines += ["", "/* 表面阶梯（唯一合法表面，禁自造中间值） */"]
    lines += [f".bg-{name} {{ background: {palette[name]}; }}" for name in TCSS_SURFACE_TOKENS]
    lines += [
        "",
        "/* 盒式语言边框三档（V1.2-1 对齐 opencode subtle/normal/active） */",
        f".border-subtle {{ border: round {palette[border_levels['subtle']]}; }}",
        f".border-normal {{ border: round {palette[border_levels['normal']]}; }}",
        f".border-active {{ border: round {palette[border_levels['active']]}; }}",
        "",
    ]
    return "\n".join(lines)


def render_tui_py(
    light: dict[str, str],
    dark: dict[str, str],
    theme_palettes: dict[str, dict[str, str]],
    theme_modes: dict[str, str],
    tokens: dict[str, Any],
    icons_flat: dict[str, str],
    sha: str,
) -> str:
    """TUI Python 常量：双档色板 + 主题视图 + css_variables() + 星符表。"""
    galaxy = tokens["color"]["galaxy"]
    tui_sec = tokens["tui"]
    border_levels = {
        level: theme_palettes[DEFAULT_THEME][name]
        for level, name in tui_sec["border_levels"].items()
    }
    type_sec = {k: v for k, v in tokens["type"].items() if k != "mono_family"}
    mono_family = tokens["type"]["mono_family"]
    themes = tuple(sorted(theme_palettes))

    def dict_lit(mapping: dict[str, Any], indent: int = 0) -> list[str]:
        pad = " " * indent
        return [f"{pad}{_py(k)}: {_py(v)}," for k, v in mapping.items()]

    def dict_lit_pretty(mapping: dict[str, Any], indent: int = 0) -> list[str]:
        """嵌套 dict 分行渲染（超 LINE_LIMIT 的嵌套节用，保产物过 ruff 110 列）。"""
        out: list[str] = []
        for key, value in mapping.items():
            inner = _py_lines(value, indent + 4)
            if len(inner) == 1:
                out.append(f"{' ' * indent}{_py(key)}: {inner[0]},")
            else:
                out.append(f"{' ' * indent}{_py(key)}: {inner[0]}")
                out.extend(inner[1:])
                out[-1] += ","
        return out

    def block(mapping: dict[str, Any], indent: int = 0) -> list[str]:
        return [f"{' ' * indent}{row}" for row in dict_lit(mapping, indent + 4)]

    lines = [
        "# -*- coding: utf-8 -*-",
        "# ============================================================",
        "# AstroForge TUI 设计常量（生成物 —— scripts/gen_design.py，禁手改）",
        f"# 源：config/design/tokens.yaml + icons.yaml（sha256:{sha}）",
        "# 消费：壳层/页面一律引用语义名（design.DARK[\"aurora\"]、design.icons.nav.home、",
        "#       design.icon(\"nav.home\")），禁散落硬编码色值与星符（§3.7 门禁 grep 断言）。",
        "# ============================================================",
        "from __future__ import annotations",
        "",
        "from types import SimpleNamespace",
        "from typing import Any",
        "",
        f"TOKENS_VERSION = {tokens.get('version', 1)}",
        f'SOURCE_SHA256 = "{sha}"',
        f'DEFAULT_THEME = "{DEFAULT_THEME}"',
        f"THEMES: tuple[str, ...] = ({', '.join(_py(t) for t in themes)},)",
        "THEME_MODE: dict[str, str] = {",
    ]
    lines += block(dict(sorted(theme_modes.items())))
    lines += [
        "}",
        "",
        "# ---- 色板（root tokens 双档解析；键=语义名，值=#RRGGBB）----",
        "LIGHT: dict[str, str] = {",
    ]
    lines += block(light)
    lines += ["}", "", "DARK: dict[str, str] = {"]
    lines += block(dark)
    lines += [
        "}",
        "",
        "# ---- 主题包解析值（点分键覆盖合并后按各主题 mode 取档；未覆盖键回落全局）----",
        "THEME_PALETTE: dict[str, dict[str, str]] = {",
    ]
    for name in themes:
        lines += [f"    {_py(name)}: {{"]
        lines += block(theme_palettes[name], 4)
        lines += ["    },"]
    lines += [
        "}",
        "",
        "def css_variables(theme: str = DEFAULT_THEME) -> dict[str, str]:",
        '    """Textual CSS 变量表：合并进 App.CSS_VARIABLES，refresh_css 瞬时切主题（§1.5）。"""',
        "    try:",
        "        return dict(THEME_PALETTE[theme])",
        "    except KeyError:",
        '        raise ValueError(f"未知主题: {theme}（可选: {\', \'.join(THEMES)}）") from None',
        "",
        "GALAXY: dict[str, Any] = {",
        f"    \"dark\": {_py(galaxy['stops'])},",
        f"    \"light\": {_py(galaxy['stopsLight'])},",
        f"    \"positions\": {_py(galaxy['positions'])},",
        "}",
        "",
    ]
    for const_name, section in (
        ("RADIUS", tokens["radius"]),
        ("SPACE", tokens["space"]),
        ("TYPE", type_sec),
        ("STARFIELD", tokens["color"]["starfield"]),
        ("MOTION_TUI", tokens["motion"]["tui"]),
        ("INTERACTION", tokens["interaction"]),  # 键盘去抖/手势阈值（§1.7 三端唯一取值处）
    ):
        lines += [f"{const_name}: dict[str, Any] = {{"]
        lines += [f"    {row}" for row in dict_lit_pretty(section, 4)]
        lines += ["}", ""]
    lines += [
        f"MONO_FAMILY = {_py(mono_family)}",
        "",
        "# tui.border_levels 三档解析值（subtle/normal/active → hex）",
        "BORDER_LEVELS: dict[str, str] = {",
    ]
    lines += block(border_levels)
    lines += [
        "}",
        f"THINKING_OPACITY = {tui_sec['thinking_opacity']}",
        "",
        "# ---- 星符表（icons.yaml；引用一律走语义名：icons.nav.home / icon(\"status.ok\")）----",
        "ICONS: dict[str, str] = {",
    ]
    lines += block(icons_flat)
    lines += [
        "}",
        "",
        "def icon(path: str) -> str:  # 例：icon(\"ai.thinking_f2\")",
        '    """按语义名取星符；未知名直接报错（宁可炸也不给错字）。"""',
        "    try:",
        "        return ICONS[path]",
        "    except KeyError:",
        '        raise ValueError(f"未知星符: {path}（可选: {len(ICONS)} 个语义名）") from None',
        "",
        "",
        "def _ns(tree: dict[str, Any]) -> Any:",
        '    """扁平点分键 → 嵌套 SimpleNamespace（icons.nav.home 属性访问）。"""',
        "    return SimpleNamespace(",
        "        **{k: (_ns(v) if isinstance(v, dict) else v) for k, v in tree.items()}",
        "    )",
        "",
        "",
        "def _icon_tree() -> dict[str, Any]:",
        "    tree: dict[str, Any] = {}",
        "    for path, glyph in ICONS.items():",
        "        parts = path.split(\".\")",
        "        node = tree",
        "        for part in parts[:-1]:",
        "            node = node.setdefault(part, {})",
        "        node[parts[-1]] = glyph",
        "    return tree",
        "",
        "",
        "icons: SimpleNamespace = _ns(_icon_tree())",
        "",
    ]
    return "\n".join(lines)


# ============================================================
# 渲染：Flutter（tokens.g.dart）
# ============================================================

def _dart_name(token: str) -> str:
    """token 名 → Dart 标识符（ink-900→ink900、gap-lg→gapLg、nav.home→navHome）。"""
    parts = re.split(r"[-_.]", token)
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def _dart_double(value: Any) -> str:
    return repr(float(value))


def render_dart(
    light: dict[str, str],
    dark: dict[str, str],
    tokens: dict[str, Any],
    icons_flat: dict[str, str],
    sha: str,
) -> str:
    """Flutter 设计契约：AstroPalette（全字段）+ lerpPalette + AstroTheme 工厂。"""
    color = tokens["color"]
    galaxy = color["galaxy"]
    starfield = color["starfield"]
    motion = tokens["motion"]["flutter"]
    interaction = tokens["interaction"]
    gesture = interaction["gesture"]
    keyboard = interaction["keyboard"]
    caps = tokens["motion"]["duration_caps"]
    type_sec = {k: v for k, v in tokens["type"].items() if k != "mono_family"}
    mono_family = tokens["type"]["mono_family"]

    names = [n for n in light if n in dark]
    galaxy_fields = ["galaxyStop0", "galaxyStop1", "galaxyStop2"]

    def const_color(hexv: str) -> str:
        return f"Color(0xFF{hexv[1:].upper()})"

    def palette_lit(palette: dict[str, str], stops: list[str]) -> list[str]:
        rows = [f"    {_dart_name(n)}: {const_color(palette[n])}," for n in names]
        rows += [f"    {f}: {const_color(stops[i])}," for i, f in enumerate(galaxy_fields)]
        return rows

    lines: list[str] = [
        "// ============================================================",
        "// AstroForge 星空设计契约（生成物 —— scripts/gen_design.py，禁手改）",
        f"// 源：config/design/tokens.yaml + icons.yaml（sha256:{sha}）",
        "// 纪律：app/lib 内除本文件外禁止 Color(0x…)（ui_doctor grep 断言）；",
        "//       主题切换走 lerpPalette 全字段插值（§1.5 TWEEN_THEME 250ms）；",
        "//       ColorScheme 手写、禁 fromSeed（星空设计系统规格 §六）。",
        "// ============================================================",
        "import 'package:flutter/material.dart';",
        "",
        "/// 星空调色板（全字段；light/dark 两实例均由 tokens.yaml 解析）。",
        "/// 字段 = 表面阶梯 + ink 阶梯 + 描边 + 五强调色（含 -Text 昼档变体）+ 实底文字",
        "/// + alpha 合成色 + 银河渐变三停驻。",
        "class AstroPalette {",
        "  const AstroPalette({",
    ]
    lines += [f"    required this.{_dart_name(n)}," for n in names]
    lines += [f"    required this.{f}," for f in galaxy_fields]
    lines += ["  });", ""]
    lines += [f"  final Color {_dart_name(n)};" for n in names]
    lines += [f"  final Color {f};" for f in galaxy_fields]
    lines += [
        "",
        "  /// 昼档（晨昏基调）。",
        "  static const AstroPalette light = AstroPalette(",
    ]
    lines += palette_lit(light, galaxy["stopsLight"])
    lines += [
        "  );",
        "",
        "  /// 夜档（深空基调，主战场）。",
        "  static const AstroPalette dark = AstroPalette(",
    ]
    lines += palette_lit(dark, galaxy["stops"])
    lines += [
        "  );",
        "}",
        "",
        "/// 全字段 lerp：主题切换 250ms 过渡（§1.5 TWEEN_THEME；经 LocalAstroPalette",
        "/// 下发时组件零改动获得同步过渡）。边界 t<=0/t>=1 直接返回端点实例。",
        "AstroPalette lerpPalette(AstroPalette a, AstroPalette b, double t) {",
        "  if (t <= 0) return a;",
        "  if (t >= 1) return b;",
        "  return AstroPalette(",
    ]
    lines += [f"    {_dart_name(n)}: Color.lerp(a.{_dart_name(n)}, b.{_dart_name(n)}, t)!," for n in names]
    lines += [
        f"    {f}: Color.lerp(a.{f}, b.{f}, t)!," for f in galaxy_fields
    ]
    lines += ["  );", "}", ""]

    # ---- 非颜色 token 常量 ----
    radius = tokens["radius"]
    space = tokens["space"]
    lines += [
        "/// 圆角四档（禁自造第五档）。",
        "abstract final class AstroRadius {",
        f"  static const double pill = {_dart_double(radius['pill'])};",
        f"  static const double lg = {_dart_double(radius['lg'])};",
        f"  static const double md = {_dart_double(radius['md'])};",
        f"  static const double sm = {_dart_double(radius['sm'])};",
        "}",
        "",
        "/// 间距（基数 4）。",
        "abstract final class AstroSpace {",
    ]
    for key, value in space.items():
        lines.append(f"  static const double {_dart_name(key)} = {_dart_double(value)};")
    lines += ["}", ""]

    steps = [
        ("display", "display"), ("h1", "h1"), ("h2", "h2"), ("title", "title"),
        ("title-sm", "titleSm"), ("body", "body"), ("body-sm", "bodySm"),
        ("caption", "caption"), ("label", "label"), ("kpi", "kpi"),
    ]
    lines += [
        "/// 字阶一步（size/height 为 dp；kpi 为 mono+tabular 仪表数字）。",
        "class AstroTypeStep {",
        "  const AstroTypeStep({required this.size, required this.height,",
        "      required this.weight, this.mono = false, this.tabular = false});",
        "",
        "  final double size;",
        "  final double height;",
        "  final FontWeight weight;",
        "  final bool mono;",
        "  final bool tabular;",
        "}",
        "",
        "/// 字阶（正文跟随系统 CJK；数字一律 mono+tabular——「仪表感」）。",
        "abstract final class AstroType {",
    ]
    for key, dart in steps:
        step = type_sec[key]
        extra = ""
        if step.get("mono") or step.get("tabular"):
            flags = []
            if step.get("mono"):
                flags.append("mono: true")
            if step.get("tabular"):
                flags.append("tabular: true")
            extra = ", " + ", ".join(flags)
        lines.append(
            f"  static const AstroTypeStep {dart} = AstroTypeStep("
            f"size: {_dart_double(step['size'])}, height: {_dart_double(step['height'])}, "
            f"weight: FontWeight.w{step['weight']}{extra});"
        )
    lines += [
        f"  static const String monoFamily = '{mono_family}';",
        "}",
        "",
        "/// 动效参数（§1.4 全局唯六，禁自造曲线）。",
        f"typedef AstroSpring = ({'{'}double stiffness, double damping{'}'});",
        "",
        "abstract final class AstroMotion {",
    ]
    for key, dart in (("spring_press", "springPress"), ("spring_soft", "springSoft"),
                      ("spring_pop", "springPop")):
        spec = motion[key]
        lines.append(
            f"  static const AstroSpring {dart} = "
            f"(stiffness: {_dart_double(spec['stiffness'])}, damping: {_dart_double(spec['damping'])});"
        )
    lines += [
        f"  static const int tweenColorMs = {motion['tween_color']['duration_ms']};",
        f"  static const int tweenMoveMs = {motion['tween_move']['duration_ms']};",
        f"  static const int tweenThemeMs = {motion['tween_theme']['duration_ms']};",
        "  static const Curve tweenEasing = Curves.fastOutSlowIn;",
        f"  static const int staggerPerItemMs = {caps['stagger_per_item_ms']};",
        f"  static const int feedbackMaxMs = {caps['feedback_max_ms']};",
        "}",
        "",
        "/// 银河渐变（白名单位 3 处，同屏 ≤1，面积 ≤6%；停驻 0%/52%/100%）。",
        "abstract final class AstroGalaxy {",
    ]
    galaxy_positions = ", ".join(_dart_double(p) for p in galaxy["positions"])
    galaxy_dark = ", ".join(const_color(v) for v in galaxy["stops"])
    galaxy_light = ", ".join(const_color(v) for v in galaxy["stopsLight"])
    sheet = gesture["sheet_dismiss"]
    drawer = gesture["drawer_open"]
    lines += [
        f"  static const List<double> positions = [{galaxy_positions}];",
        f"  static const List<Color> darkStops = [{galaxy_dark}];",
        f"  static const List<Color> lightStops = [{galaxy_light}];",
    ]
    lines += [
        "}",
        "",
        "/// 星野参数（坐标见 config/design/starfield/seed.json，预生成禁每帧随机）。",
        "abstract final class AstroStarfield {",
        f"  static const List<double> alphaSteps = "
        f"[{', '.join(_dart_double(v) for v in starfield['alpha_steps'])}];",
        f"  static const List<double> sizeSteps = "
        f"[{', '.join(_dart_double(v) for v in starfield['size_steps'])}];",
        f"  static const int densityMin = {starfield['density'][0]};",
        f"  static const int densityMax = {starfield['density'][1]};",
        f"  static const double driftDp = {_dart_double(starfield['drift_dp'])};",
        f"  static const double driftPeriodS = {_dart_double(starfield['drift_period_s'])};",
        f"  static const int meteorIntervalS = {starfield['meteor_interval_s']};",
        f"  static const int meteorDurationMs = {starfield['meteor_duration_ms']};",
        "}",
        "",
        "/// 交互参数（§1.7 三端唯一取值处）。",
        "abstract final class AstroInteraction {",
        f"  static const double hitMinDp = {_dart_double(interaction['hit_min_dp'])};",
        f"  static const double sheetDismissDistanceDp = {_dart_double(sheet['distance_dp'])};",
        f"  static const double sheetDismissVelocityDps = {_dart_double(sheet['velocity_dps'])};",
        f"  static const double drawerOpenDistanceRatio = {_dart_double(drawer['distance_ratio'])};",
        f"  static const double drawerOpenVelocityDps = {_dart_double(drawer['velocity_dps'])};",
        f"  static const int longPressMs = {gesture['long_press_ms']};",
        f"  static const double slopDp = {_dart_double(gesture['slop_dp'])};",
        f"  static const double swipeConfirmRatio = {_dart_double(gesture['swipe_confirm_ratio'])};",
        f"  static const int navDebounceMs = {keyboard['nav_debounce_ms']};",
        f"  static const int paletteDebounceMs = {keyboard['palette_debounce_ms']};",
        "}",
        "",
        "/// 星符表（icons.yaml；文本内嵌星符一律取自此处，禁散落硬编码）。",
        "abstract final class AstroIcons {",
    ]
    for path, glyph in icons_flat.items():
        lines.append(f"  static const String {_dart_name(path)} = '{glyph}';")
    lines += [
        "}",
        "",
        "/// 主题工厂（替代 theme.dart；夜档零投影、层级靠明度——规格 §二/§六）。",
        "class AstroTheme {",
        "  AstroTheme._();",
        "",
        "  static ThemeData light() => _build(AstroPalette.light, Brightness.light);",
        "",
        "  static ThemeData dark() => _build(AstroPalette.dark, Brightness.dark);",
        "",
        "  static ThemeData _build(AstroPalette p, Brightness brightness) {",
        "    final isDark = brightness == Brightness.dark;",
        "    final scheme = ColorScheme(",
        "      brightness: brightness,",
        "      primary: p.aurora,",
        "      onPrimary: p.onAurora,",
        "      primaryContainer: p.chipsSelectedBg,",
        "      onPrimaryContainer: isDark ? p.aurora : p.auroraText,",
        "      secondary: p.nebula,",
        "      onSecondary: p.onNebula,",
        "      secondaryContainer: p.aiContainerBg,",
        "      onSecondaryContainer: isDark ? p.nebula : p.nebulaText,",
        "      tertiary: p.hydrogen,",
        "      onTertiary: p.onHydrogen,",
        "      error: p.nova,",
        "      onError: p.onNova,",
        "      errorContainer: p.errorWashBg,",
        "      onErrorContainer: p.nova,",
        "      surface: p.card,",
        "      onSurface: p.ink900,",
        "      onSurfaceVariant: p.ink600,",
        "      surfaceContainerLowest: p.bg,",
        "      surfaceContainerLow: p.card,",
        "      surfaceContainer: p.container,",
        "      surfaceContainerHigh: p.cardRaised,",
        "      surfaceContainerHighest: p.containerPressed,",
        "      outline: p.stroke,",
        "      outlineVariant: p.faint,",
        "      shadow: const Color(0x00000000),",
        "      scrim: p.bg.withAlpha(179), // bg@70%（弹层 scrim）",
        "    );",
        "    return ThemeData(",
        "      useMaterial3: true,",
        "      colorScheme: scheme,",
        "      scaffoldBackgroundColor: p.bg,",
        "      // 夜档零投影：组件级 elevation 恒 0（card 等），层级靠明度不靠描边/投影",
        "      cardTheme: CardThemeData(",
        "        elevation: 0,",
        "        color: p.card,",
        "        shape: RoundedRectangleBorder(",
        "          borderRadius: BorderRadius.circular(AstroRadius.md)),",
        "      ),",
        "      dividerTheme: DividerThemeData(",
        "        color: p.faint.withAlpha(179), // faint 仅表格行分隔 @70%",
        "        thickness: 1.0,",
        "        space: 1.0,",
        "      ),",
        "      inputDecorationTheme: InputDecorationTheme(",
        "        filled: true,",
        "        fillColor: p.sunken,",
        "        isDense: true,",
        "        enabledBorder: OutlineInputBorder(",
        "          borderRadius: BorderRadius.circular(AstroRadius.sm),",
        "          borderSide: BorderSide(color: p.stroke, width: 1.0),",
        "        ),",
        "        focusedBorder: OutlineInputBorder(",
        "          borderRadius: BorderRadius.circular(AstroRadius.sm),",
        "          borderSide: BorderSide(color: p.aurora, width: 1.5), // 焦点=aurora 1.5dp",
        "        ),",
        "        errorBorder: OutlineInputBorder(",
        "          borderRadius: BorderRadius.circular(AstroRadius.sm),",
        "          borderSide: BorderSide(color: p.nova, width: 1.5),",
        "        ),",
        "        focusedErrorBorder: OutlineInputBorder(",
        "          borderRadius: BorderRadius.circular(AstroRadius.sm),",
        "          borderSide: BorderSide(color: p.nova, width: 1.5),",
        "        ),",
        "      ),",
        "      navigationRailTheme: NavigationRailThemeData(",
        "        backgroundColor: p.bg,",
        "        useIndicator: true,",
        "        indicatorColor: p.aurora,",
        "        indicatorShape: const StadiumBorder(),",
        "        selectedIconTheme: IconThemeData(color: p.onAurora),",
        "        unselectedIconTheme: IconThemeData(color: p.ink600),",
        "        selectedLabelTextStyle: TextStyle(color: p.ink900, fontWeight: FontWeight.w600),",
        "        unselectedLabelTextStyle: TextStyle(color: p.ink600),",
        "      ),",
        "      chipTheme: ChipThemeData(",
        "        backgroundColor: p.container,",
        "        selectedColor: p.chipsSelectedBg,",
        "        side: BorderSide(color: p.stroke),",
        "        shape: RoundedRectangleBorder(",
        "          borderRadius: BorderRadius.circular(AstroRadius.pill)),",
        "        labelStyle: TextStyle(color: p.ink900),",
        "      ),",
        "      dialogTheme: DialogThemeData(",
        "        backgroundColor: p.cardRaised,",
        "        shape: RoundedRectangleBorder(",
        "          borderRadius: BorderRadius.circular(AstroRadius.lg)),",
        "      ),",
        "      tabBarTheme: TabBarThemeData(",
        "        labelColor: p.ink900,",
        "        unselectedLabelColor: p.ink600,",
        "        indicatorColor: p.aurora,",
        "        dividerColor: Colors.transparent,",
        "      ),",
        "      tooltipTheme: TooltipThemeData(",
        "        decoration: BoxDecoration(",
        "          color: p.cardRaised,",
        "          borderRadius: BorderRadius.circular(AstroRadius.sm)),",
        "        textStyle: TextStyle(color: p.ink900, fontSize: AstroType.caption.size),",
        "      ),",
        "      snackBarTheme: SnackBarThemeData(",
        "        backgroundColor: p.cardRaised,",
        "        contentTextStyle: TextStyle(color: p.ink900),",
        "        behavior: SnackBarBehavior.floating,",
        "        shape: RoundedRectangleBorder(",
        "          borderRadius: BorderRadius.circular(AstroRadius.sm)),",
        "      ),",
        "      popupMenuTheme: PopupMenuThemeData(",
        "        color: p.cardRaised,",
        "        shape: RoundedRectangleBorder(",
        "          borderRadius: BorderRadius.circular(AstroRadius.sm)),",
        "      ),",
        "      switchTheme: SwitchThemeData(",
        "        thumbColor: WidgetStatePropertyAll(p.onAurora),",
        "        trackColor: WidgetStatePropertyAll(p.chipsSelectedBg),",
        "      ),",
        "      checkboxTheme: CheckboxThemeData(",
        "        fillColor: WidgetStatePropertyAll(p.aurora),",
        "        checkColor: WidgetStatePropertyAll(p.onAurora),",
        "        side: BorderSide(color: p.stroke),",
        "      ),",
        "    );",
        "  }",
        "}",
        "",
    ]
    return "\n".join(lines)


# ============================================================
# 渲染：CLI（star_console.py 顶部生成段）
# ============================================================

def render_star_console_segment(light: dict[str, str], dark: dict[str, str],
                                tokens: dict[str, Any], icons_flat: dict[str, str],
                                sha: str) -> str:
    """star_console.py 的「星空设计 token」生成段（标记内的全部内容）。"""
    galaxy = tokens["color"]["galaxy"]
    lines = [
        STAR_CONSOLE_BEGIN,
        f"# 源：config/design/tokens.yaml + icons.yaml（sha256:{sha}）",
        "# 消费：CLI 全部颜色/星符一律取自本段（裸色/裸星符=违反设计契约）；",
        "#       富文本色用 STAR_TOKENS，纯文本降级路径不取色（字节契约不变）。",
        "STAR_TOKENS: dict[str, dict[str, str]] = {",
    ]
    for mode, palette in (("dark", dark), ("light", light)):
        lines.append(f'    "{mode}": {{')
        lines += [f"        {_py(k)}: {_py(v)}," for k, v in palette.items()]
        lines.append("    },")
    lines += [
        "}",
        "STAR_GALAXY: dict[str, list[str]] = {",
        f'    "dark": {_py(galaxy["stops"])},',
        f'    "light": {_py(galaxy["stopsLight"])},',
        "}",
        "STAR_ICONS: dict[str, str] = {",
    ]
    lines += [f"    {_py(k)}: {_py(v)}," for k, v in icons_flat.items()]
    lines += ["}", STAR_CONSOLE_END]
    return "\n".join(lines)


def render_star_console(existing_text: str | None, segment: str) -> str:
    """整文件内容：已有文件只替换标记段（手写部分不动）；新文件=前导+段+尾部助手。"""
    if (
        existing_text is not None
        and STAR_CONSOLE_BEGIN in existing_text
        and STAR_CONSOLE_END in existing_text
    ):
        head = existing_text.split(STAR_CONSOLE_BEGIN, 1)[0]
        tail = existing_text.split(STAR_CONSOLE_END, 1)[1]
        return f"{head}{segment}{tail}"
    return STAR_CONSOLE_PREAMBLE + segment + STAR_CONSOLE_TAIL


# ============================================================
# 汇总：渲染全部产物 / 落盘
# ============================================================

def source_sha256(repo_root: Path) -> str:
    """tokens+icons 内容指纹（进生成物头注释：源变则产物必变，契约可追溯）。"""
    design_dir = repo_root / "config" / "design"
    digest = hashlib.sha256()
    for name in ("tokens.yaml", "icons.yaml"):
        digest.update((repo_root / "config" / "design" / name).read_bytes())
    for extra in sorted((design_dir / "themes").glob("*/tokens.yaml")):
        digest.update(extra.read_bytes())
    return digest.hexdigest()[:12]


def build_artifacts(repo_root: Path, star_seed: int = DEFAULT_STAR_SEED) -> dict[str, str]:
    """渲染全部产物（相对路径 → 文本）。纯函数不落盘：generate_all 落盘、单测比对。"""
    bundle = load_bundle(repo_root)
    validate_bundle(bundle)
    tokens = bundle["tokens"]
    color = tokens["color"]
    light = palette_of(color, "light")
    dark = palette_of(color, "dark")

    theme_palettes: dict[str, dict[str, str]] = {}
    theme_modes: dict[str, str] = {}
    for name, raw in bundle["themes"].items():
        theme_palettes[name] = theme_palette(tokens, raw)
        theme_modes[name] = (raw.get("meta") or {}).get("mode") or "dark"
    if DEFAULT_THEME not in theme_palettes and theme_palettes:
        default = sorted(theme_palettes)[0]
        raise DesignValidationError(f"默认主题 {DEFAULT_THEME} 不在 themes/（首个候选 {default}）")

    icons_flat = flatten_icons(bundle["icons"])
    sha = source_sha256(repo_root)
    default_palette = theme_palettes[DEFAULT_THEME]

    starfield = render_starfield(star_seed, color["starfield"]["density"])
    seed_text = json.dumps(starfield, ensure_ascii=False, indent=2) + "\n"

    cli_path = repo_root / ARTIFACT_CLI
    existing_cli = cli_path.read_text(encoding="utf-8") if cli_path.exists() else None

    return {
        ARTIFACT_TCSS: render_tui_tcss(default_palette, tokens["tui"]["border_levels"], sha),
        ARTIFACT_TPY: render_tui_py(light, dark, theme_palettes, theme_modes, tokens, icons_flat, sha),
        ARTIFACT_DART: render_dart(light, dark, tokens, icons_flat, sha),
        ARTIFACT_CLI: render_star_console(
            existing_cli,
            render_star_console_segment(light, dark, tokens, icons_flat, sha),
        ),
        ARTIFACT_SEED: seed_text,
    }


TUI_PACKAGE_INITS = {
    "tui/tui/theme/__init__.py": (
        "# -*- coding: utf-8 -*-\n"
        '"""TUI 主题包：generated/ 下的 tokens.tcss / tokens.py 由 scripts/gen_design.py 生成。"""\n'
    ),
    "tui/tui/theme/generated/__init__.py": (
        "# -*- coding: utf-8 -*-\n"
        '"""设计契约生成物（scripts/gen_design.py 输出，禁手改；源 config/design/）。"""\n'
    ),
}


def generate_all(repo_root: Path = REPO_ROOT, star_seed: int = DEFAULT_STAR_SEED) -> dict[str, bool]:
    """落盘全部产物（仅内容变化时写，保持幂等）；返回 {相对路径: 是否有写入}。"""
    artifacts = build_artifacts(repo_root, star_seed)
    written: dict[str, bool] = {}
    for rel, text in artifacts.items():
        path = repo_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        written[rel] = not path.exists() or path.read_text(encoding="utf-8") != text
        if written[rel]:
            path.write_text(text, encoding="utf-8", newline="\n")
    for rel, text in TUI_PACKAGE_INITS.items():
        path = repo_root / rel
        if not path.exists():  # 包骨架只补不改（手写区）
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="AstroForge 设计契约渲染器（config/design → TUI/Flutter/CLI 三端产物）"
    )
    parser.add_argument(
        "--seed", type=int, default=DEFAULT_STAR_SEED,
        help=f"星野种子（默认 {DEFAULT_STAR_SEED}；种子决定 60~90 颗星点的确定性坐标）",
    )
    args = parser.parse_args(argv)

    try:
        bundle = load_bundle(REPO_ROOT)
        themes = ", ".join(sorted(bundle["themes"])) or "（无）"
        validate_bundle(bundle)
        written = generate_all(REPO_ROOT, star_seed=args.seed)
    except DesignValidationError as exc:
        print(f"[gen_design] {exc}", file=sys.stderr)
        return 2

    for rel in ARTIFACTS:
        mark = "写入" if written.get(rel) else "未变"
        print(f"[gen_design] {mark}  {rel}")
    print(f"[gen_design] 主题包: {themes}（默认 {DEFAULT_THEME}）")
    print("[gen_design] 纪律：tokens.yaml 任一变更必须重跑本脚本（CI diff=0 门禁）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
