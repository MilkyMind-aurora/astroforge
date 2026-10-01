# CI 红灯演练留档（gen-idempotent / 设计契约门禁）

> 终审遗留 [L1]：CI 红灯演练无留档。本文件记录一次真实执行的红灯演练：
> 只改 `config/design/tokens.yaml` 不重新生成 → 提交这种「源与产物脱节」的变更时，
> `design` job 的设计契约门禁（gen-idempotent，`ci.yml` 的「设计契约门禁」步骤）必须红灯。

## 演练口径

- **基线提交**：`dc46462`（MF6 星空版收口），演练树工作区起始干净。
- **隔离方式**：`git worktree`（`git worktree add --detach astroforge_ci_drill_tmp HEAD`），
  等同 CI 全新 checkout；主工作树当时有其他组并行施工的未提交改动，故不在主树演练。
  所用 `scripts/gen_design.py` 为 HEAD 提交版（非工作树未提交版）。
- **环境**：Windows 11 + git-bash；Python 3.12.10（仓库 `.venv`：pyyaml 6.0.3）。
- **演练后复原**：演练树整体 `git worktree remove --force` 移除，主工作树零接触。

## 红灯复现

1) 只改源不重新生成（模拟会闯红灯的提交方式）：

```text
tokens.yaml 已改：aurora.dark #4EE0C0 -> #22C0A0（模拟只改源不重新生成后提交）
```

对应 diff（`config/design/tokens.yaml` 第 37 行）：

```diff
-  aurora:            { light: "#0C9B7E", dark: "#4EE0C0" }   # 选中/主按钮/进度/运行中/今日点
+  aurora:            { light: "#0C9B7E", dark: "#22C0A0" }   # 选中/主按钮/进度/运行中/今日点
```

2) 跑 `python scripts/gen_design.py`（CI design job 同款步骤），再执行 CI 门禁原样命令：

```bash
status="$(git status --porcelain -- tui app modules config/design)"
if [ -n "$status" ]; then
  echo "设计产物与提交不同步（改 tokens.yaml 后必须重跑 scripts/gen_design.py）："
  echo "$status"
  exit 1
fi
```

输出节选（红灯证据）：

```text
=== 复现 CI design job 门禁（bash 同款逻辑）===
设计产物与提交不同步（改 tokens.yaml 后必须重跑 scripts/gen_design.py）：
 M app/lib/core/design/tokens.g.dart
 M config/design/tokens.yaml
 M modules/_shared/star_console.py
 M tui/tui/theme/generated/tokens.py
 M tui/tui/theme/generated/tokens.tcss
gate-exit=1
```

即：若开发者提交了新的 `tokens.yaml` 而未随附重新生成的产物，CI 的
「设计契约门禁（tokens 变更必须随附再生成，diff=0）」步骤以退出码 1 红灯，
与本地演练一致。生成物头部的「源 sha256」指纹（如
`star_console.py` 顶部 `sha256:06b559db8ba2`）随源字节联动，是同一门禁的第二道印证。

## 复原

```bash
git checkout -- .          # 丢弃演练改动（源 + 生成物一并复原）
git status --porcelain     # 输出为空 → 工作树回到基线
```

实测：checkout 后 `git status --porcelain` 为空（复原完成），门禁不再拦。

## 环境观察（不影响 CI，供 Windows 本机开发参考）

演练树（`core.autocrlf=true`）里，复原后再跑 `gen_design` 会使 4 个生成物显示
`M`：生成物头部嵌的「源 sha256」按 `config/design/tokens.yaml` 的**原始字节**计算，
而 `.gitattributes` 未对该 yaml 强制 `eol=lf`，autocrlf 检出为 CRLF 后指纹即漂移
（实测 worktree 文件 sha256 前 16 位 `852f398fcbbdb0f7` ≠ HEAD blob `3bedfd59858ec67e`）。
CI 的 ubuntu runner 按 LF 检出，不受影响；Windows 本机开发建议保持 tokens.yaml 为 LF，
或由工具链在 `.gitattributes` 补 `config/design/*.yaml text eol=lf`（本演练未改动，
属工具链组范围）。
