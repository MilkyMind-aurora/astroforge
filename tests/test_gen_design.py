# -*- coding: utf-8 -*-
"""设计契约单测（V1-B.1/B.2 DoD）：点分键覆盖合并语义 + 三端生成物一致性 + 星野种子。

覆盖合并语义与 server config_loader 的 platform_overrides 同构（方案 §2.2），
此处对 gen_design 的合并器独立验证——两个消费方共用同一套语义约定。
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import gen_design  # noqa: E402,I001


# ============================================================
# 点分键覆盖合并（platform_overrides 同语义）
# ============================================================

def test_set_dotted_覆盖与回落() -> None:
    data = {"a": {"b": 1, "c": 2}}
    gen_design.set_dotted(data, "a.b", 9)
    assert data == {"a": {"b": 9, "c": 2}}  # 覆盖 a.b，a.c 回落原值
    gen_design.set_dotted(data, "x.y.z", "new")  # 新路径自动建层
    assert data["x"]["y"]["z"] == "new"


def test_set_dotted_标量冲突必须报错() -> None:
    data = {"a": "scalar"}
    with pytest.raises(ValueError, match="键冲突"):
        gen_design.set_dotted(data, "a.b.c", 1)


def test_flatten_dotted_嵌套与点分键等价() -> None:
    nested = {"color": {"bg": "#FFF", "ink": {"light": 1}}}
    dotted = {"color.bg": "#FFF", "color.ink.light": 1}
    assert gen_design.flatten_dotted(nested) == gen_design.flatten_dotted(dotted)


def test_merge_theme_覆盖单值未覆盖回落() -> None:
    root = {"color": {"bg": {"light": "#F6F7FC", "dark": "#05070F"},
                      "aurora": {"light": "#0C9B7E", "dark": "#4EE0C0"}}}
    theme = {"meta": {"mode": "light"}, "color": {"bg": "#ABCDEF"}}
    merged = gen_design.merge_theme(root, theme)
    assert merged["color"]["bg"] == "#ABCDEF"          # 点分键覆盖（整值替换）
    assert merged["color"]["aurora"] == root["color"]["aurora"]  # 未覆盖回落
    assert root["color"]["bg"]["dark"] == "#05070F"    # 根 tokens 不被原地改写


def test_theme_palette_按主题档取值() -> None:
    tokens = gen_design.load_bundle(REPO_ROOT)["tokens"]
    dawn = gen_design.theme_palette(tokens, gen_design.load_bundle(REPO_ROOT)["themes"]["dawn"])
    deep = gen_design.theme_palette(tokens, gen_design.load_bundle(REPO_ROOT)["themes"]["deep-space"])
    assert dawn["bg"] == "#F6F7FC"      # dawn（light 档 + bg 覆盖）
    assert deep["bg"] == "#05070F"      # deep-space 空覆盖 → 全局 dark 档
    assert deep["aurora"] == "#4EE0C0"  # 未覆盖键回落全局


# ============================================================
# 星野种子（60~90 颗确定性坐标）
# ============================================================

def test_starfield_同种子确定且边界合法() -> None:
    density = [60, 90]
    a = gen_design.render_starfield(123, density)
    b = gen_design.render_starfield(123, density)
    assert a == json.loads(json.dumps(a))  # 可序列化
    assert 60 <= a["count"] <= 90
    assert a == b, "同种子两次生成必须逐字节一致"
    for star in a["stars"]:
        assert 0.0 <= star["x"] < 1.0 and 0.0 <= star["y"] < 1.0
        assert star["tier"] in (0, 1, 2)
        assert 0.0 <= star["phase"] < 4.0


# ============================================================
# 三端生成物：tmp 树全量生成 + 幂等 + star_console 段替换
# ============================================================

@pytest.fixture()
def tmp_repo(tmp_path: Path) -> Path:
    """最小可生成仓库树：config/design 全套资产拷入 tmp（星野种子除外，验证全新生成）。"""
    shutil.copytree(REPO_ROOT / "config" / "design", tmp_path / "config" / "design")
    shutil.rmtree(tmp_path / "config" / "design" / "starfield", ignore_errors=True)
    return tmp_path


def test_generate_all_产物齐全且幂等(tmp_repo: Path) -> None:
    written_first = gen_design.generate_all(tmp_repo)
    assert set(written_first) == set(gen_design.ARTIFACTS)
    assert all(written_first.values()), "首次生成应全部落盘"
    for rel in gen_design.ARTIFACTS:
        assert (tmp_repo / rel).exists(), f"缺产物 {rel}"
    # 生成物内容一致性与幂等：第二次全部「未变」
    written_second = gen_design.generate_all(tmp_repo)
    assert not any(written_second.values()), f"幂等破坏: {[k for k, v in written_second.items() if v]}"
    # 生成物头部带源指纹（tokens 变则产物必变）
    text = (tmp_repo / gen_design.ARTIFACT_TPY).read_text(encoding="utf-8")
    assert "SOURCE_SHA256" in text and "sha256:" in text


def test_generate_all_生成物可直接导入(tmp_repo: Path) -> None:
    gen_design.generate_all(tmp_repo)
    sys.path.insert(0, str(tmp_repo / "tui"))
    try:
        from tui.theme.generated import tokens as design

        assert design.DARK["aurora"] == "#4EE0C0"
        assert design.icons.nav.home == "✦"
        assert design.icon("task.success") == "✓"
        with pytest.raises(ValueError, match="未知星符"):
            design.icon("nav.nonexistent")
        assert design.css_variables("dawn")["bg"] == "#F6F7FC"
    finally:
        sys.path.remove(str(tmp_repo / "tui"))
        sys.modules.pop("tui.theme.generated.tokens", None)
        sys.modules.pop("tui.theme.generated", None)
        sys.modules.pop("tui.theme", None)
        sys.modules.pop("tui", None)


def test_star_console_只替换生成段不动手写区(tmp_repo: Path) -> None:
    gen_design.generate_all(tmp_repo)
    cli = tmp_repo / gen_design.ARTIFACT_CLI
    text = cli.read_text(encoding="utf-8")
    assert gen_design.STAR_CONSOLE_BEGIN in text and gen_design.STAR_CONSOLE_END in text
    assert "降级纪律" in text and "def palette(" in text  # 手写前导/尾部俱在
    # 模拟 MF3 之后的手写扩展：在段外追加渲染器代码，重跑生成必须保留
    text += '\n\ndef banner(module: str) -> str:\n    """MF3 渲染器占位（手写区）。"""\n    return module\n'
    cli.write_text(text, encoding="utf-8", newline="\n")
    gen_design.generate_all(tmp_repo)
    assert "def banner(" in cli.read_text(encoding="utf-8"), "生成段替换不得动手写区"


def test_validate_台词超长必须拒绝(tmp_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    quotes = tmp_repo / "config" / "design" / "quotes.yaml"
    raw = quotes.read_text(encoding="utf-8")
    raw += '\n  test_overlong:\n    lines:\n'
    raw += '      - "这条台词故意写得非常非常长用来触发二十四个字符上限校验规则"\n'
    quotes.write_text(raw, encoding="utf-8", newline="\n")
    with pytest.raises(gen_design.DesignValidationError, match="校验失败"):
        gen_design.build_artifacts(tmp_repo)
    assert "超 24 字" in capsys.readouterr().err


def test_validate_缺色token必须拒绝(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    tokens_file = tmp_repo / "config" / "design" / "tokens.yaml"
    raw = tokens_file.read_text(encoding="utf-8")
    raw = raw.replace("  aurora:", "  auroraX:", 1)  # 抽走一个必需 token
    tokens_file.write_text(raw, encoding="utf-8", newline="\n")
    with pytest.raises(gen_design.DesignValidationError, match="校验失败"):
        gen_design.build_artifacts(tmp_repo)
    assert "缺色 token color.aurora" in capsys.readouterr().err


# ============================================================
# 仓库契约：提交的生成物必须与源同步（CI diff=0 的单测面）
# ============================================================

def test_repo_artifacts_与源同步() -> None:
    artifacts = gen_design.build_artifacts(REPO_ROOT)
    stale = [
        rel for rel, text in artifacts.items()
        if (REPO_ROOT / rel).read_text(encoding="utf-8") != text
    ]
    assert not stale, (
        f"生成物与 config/design 不同步（改源后必须重跑 scripts/gen_design.py）: {stale}"
    )
