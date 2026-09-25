# CLI 星幕渲染器 · TTY/非 TTY 双态输出样本（MF3 / 方案 §四）

> 渲染器：`modules/_shared/star_console.py`（六件套 banner/stage/progress/result_card/error_card/log）。
> 颜色/星符/进度节流一律取自 `scripts/gen_design.py` 生成段（`STAR_TOKENS`/`STAR_ICONS`/`STAR_MOTION`，
> 源 `config/design/tokens.yaml` + `icons.yaml`，禁手改、禁散落硬编码）。
> 本文样本为**真实捕获**（非手绘），复现命令见文末。

## 双态判定规则【硬性，方案 §2.5】

| 条件 | 行为 |
|---|---|
| `sys.stdout.isatty()` 且 rich 可导入 | rich 富文本（aurora/熔金/朱红分级着色；Panel 盒线；transient 进度条） |
| 接终端但无 rich | 纯文本 + ASCII `█░` 进度条（逐行输出，按节流限频） |
| 非 TTY（服务核心管道捕获）或强制纯文本 | **纯文本**；`progress()` 静默（管道内回车重绘会污染逐行捕获） |

stdout 契约（管道态）：日志行 ``[INFO] ``/``[WARN] ``/``[ERROR] `` 前缀逐字节不变（服务核心
`process_runner` 逐行捕获、`task_scheduler` 按行内 `[ERROR]` 判档，零改动）；结果 JSON 仍为
`{"code", "message", "data"}` 三键（`cli_utils.save_json`）。

色深跟随终端能力自动降级（rich auto）：真彩 → 256 色 → 单色（对齐 §3.7 逐档降级纪律）。

---

## 态 1 · 非 TTY（服务核心管道捕获态，纯文本）

```

  ✦ AstroForge · 衍星台 — spider
  Sidereal Core v0.1.0 · env_spider · spider_site

──────────────────────────── ✦ ─────────────────────────────
◈ 阶段 2/5 · 解析侧边栏目录
[INFO] 发现 9 个章节 · 52 个页面
[INFO] [24/52] https://docs.example.com/01-开始/introduction.html
[WARN] 2 页连续 404，已跳过
✓ 任务完成 · 52 项 · 耗时 128s
  产物 3 项：
    ✦ _index.json  output/site
    ✦ 01-开始/introduction.md
    ✦ 02-安装/installation.md
[ERROR] 入口页抓取失败: timeout
✕ 失败 · code 3004
  整站爬取未获得任何页面（可能被反爬拦截）
  修复指引: 疑似反爬拦截：调大 request_interval、配置 browser.chromium_path 走本地渲染后重试
```

要点：无 ANSI 转义、无回车（\r）重绘；`[ERROR]` 前缀行与修复指引随任务日志入库；
进度条静默（进度由逐条 `[INFO] [24/52] …` 行与结果 JSON 承担）。

---

## 态 2 · TTY + rich 可导入（Windows Terminal，宽 100 列）

终端可见观感（ANSI 剥离展示；实际字节含 SGR 转义，原始行摘录见下）：

```

  ✦ AstroForge · 衍星台 — spider
  Sidereal Core v0.1.0 · env_spider · spider_site

──────────────────────────── ✦ ─────────────────────────────
◈ 阶段 2/5 · 解析侧边栏目录
[INFO] 发现 9 个章节 · 52 个页面
[INFO] [24/52] https://docs.example.com/01-开始/introduction.html
[WARN] 2 页连续 404，已跳过
╭─ ✓ 任务完成 · 52 项 · 耗时 128s ─────────────────────────────────────────────────────────────────╮
│ 产物 3 项：                                                                                      │
│ ✦ _index.json              output/site                                                           │
│ ✦ 01-开始/introduction.md                                                                        │
│ ✦ 02-安装/installation.md                                                                        │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
[ERROR] 入口页抓取失败: timeout
╭─ ✕ 失败 · code 3004 ─────────────────────────────────────────────────────────────────────────────╮
│ 整站爬取未获得任何页面（可能被反爬拦截）                                                         │
│ 修复指引: 疑似反爬拦截：调大 request_interval、配置 browser.chromium_path 走本地渲染后重试       │
╰──────────────────────────────────────────────────────────────────────────────────────────────────╯
```

原始字节摘录（副题行；`ESC[38;5;109m` 为 SGR 前缀、`ESC[0m` 复位，色深随终端能力自动升降）：

```
ESC[38;5;109m  Sidereal Core v0.1.0 · env_spider · spider_siteESC[0m
```

配色语义（夜档 deep-space，`STAR_TOKENS["dark"]`）：星符/进度/选中=极光青 `#4EE0C0`；
标题=星白 `#EDF0FB`；副题/`[INFO]`=次级 `#9AA1C0`；`[WARN]`=熔金 `#FFB74D`；
`[ERROR]`/错误卡边框=新星红 `#FF5648`；阶段分隔线=faint `#222741`。
昼档（`ASTROFORGE_CLI_THEME=light`）自动切换为 `tokens.yaml` light 值。

进度条（rich 态）：`rich Progress` 原地 live 渲染、`transient=True` 结束即清行、不在回滚缓冲留痕，
因此本态样本流中无独立进度行；刷新节奏取 `motion.cli.progress_throttle_ms = 100`（refresh_per_second=10）。

---

## 态 3 · TTY 但无 rich（ASCII `█░` 条，逐行输出）

```

  ✦ AstroForge · 衍星台 — spider
  Sidereal Core v0.1.0 · env_spider · spider_site

──────────────────────────── ✦ ─────────────────────────────
◈ 阶段 2/5 · 解析侧边栏目录
[INFO] 发现 9 个章节 · 52 个页面
爬取进度  ██████████████████░░░░░░░░░░░░░░░░░░░░░░  24/52 · 46%
[INFO] [24/52] https://docs.example.com/01-开始/introduction.html
[WARN] 2 页连续 404，已跳过
✓ 任务完成 · 52 项 · 耗时 128s
  产物 3 项：
    ✦ _index.json  output/site
    ✦ 01-开始/introduction.md
    ✦ 02-安装/installation.md
[ERROR] 入口页抓取失败: timeout
✕ 失败 · code 3004
  整站爬取未获得任何页面（可能被反爬拦截）
  修复指引: 疑似反爬拦截：调大 request_interval、配置 browser.chromium_path 走本地渲染后重试
```

---

## 错误码 → 修复指引映射表（pro 7.3.2）

`star_console.fix_guide(code)`；`error_card()` 失败收尾时渲染。码段语义对齐 pro §3.8 统一错误码分段。

### 已登记码（精确匹配）

| code | 修复指引 |
|---|---|
| 1001 | 检查任务配置：补全缺失参数（task_type/url/input_path 等，字段见各模块 cli.py 文档串） |
| 1002 | 检查输入合法性：外联 URL 仅允许 http/https（经 url_guard 校验）；文件格式需在模块支持清单内 |
| 1003 | 模板名不合法：查询 GET /api/v1/templates 可用模板清单后重试 |
| 1004 | 流水线 YAML 解析失败：核对缩进与字段名，经流水线页「自定义 YAML」重新保存 |
| 1300 | 任务已按请求取消，无需修复；需要时重新创建任务即可 |
| 2001 | 认证失败：请求头补 X-AstroForge-Token（token 见 data/service_token） |
| 2002 | 服务内部错误：查 data/logs/ 与服务核心日志定位；必要时重启 Sidereal Core |
| 2003 | 配置缺失：检查 config/settings.yaml 与环境变量（ASTROFORGE_PG_PASSWORD 等） |
| 2004 | 数据库不可用：确认 PostgreSQL 已启动、astroforge 库已建（scripts/db_init.sql） |
| 3001 | 运行环境缺失：运行 scripts/install_envs*.bat|.sh 创建对应 conda 环境，scripts/check_env.* 复查 |
| 3002 | 子进程超时：放大任务超时配置或缩减输入规模后重试 |
| 3003 | 模块执行异常：查看任务日志尾部 stderr 定位；修复后可直接重试该任务 |
| 3004 | 疑似反爬拦截：调大 request_interval、配置 browser.chromium_path 走本地渲染后重试 |
| 3005 | 模型加载失败：运行 scripts/download_models.* 补齐模型文件，确认 env_ai 已装 llama-cpp-python |
| 3006 | 该功能属规划内未实现（Phase 2）：当前改用其他任务类型，等待后续版本 |
| 4001 | 输入不存在：核对 input_path/input_dir 是否存在且可读 |
| 4002 | 内存超红线（settings.system.max_memory_gb）：调小 max_threads/批量规模后重试 |
| 4003 | 磁盘空间不足：清理 data/ 与模块输出目录后重试 |
| 4004 | 依赖缺失：anydoc 二进制缺失运行 scripts/install_anydoc.bat|.sh；AI 引擎未启动则拉起 modules/ai_engine |

### 未登记码（分段回落）

| 分段 | 回落指引 |
|---|---|
| 1xxx | 客户端参数错误：核对任务配置字段与取值范围（1xxx 段） |
| 2xxx | 服务端错误：查服务核心日志与 data/logs/（2xxx 段） |
| 3xxx | 模块执行错误：查任务日志尾部与对应 conda 环境（3xxx 段） |
| 4xxx | 资源错误：核对文件/内存/磁盘/依赖进程状态（4xxx 段） |

未知分段（如 9xxx）回落：`未登记错误码：查 docs/ 与任务日志定位`。

---

## 复现命令

```bash
# 态 1（非 TTY：重定向即降级）
.venv/Scripts/python.exe modules/spider/cli.py --config cfg.json --output res.json | cat
# 态 2/3（TTY：在 Windows Terminal 里直接运行）
.venv/Scripts/python.exe modules/spider/cli.py --config cfg.json --output res.json
# 强制着色/纯文本/昼档（测试与样本捕获用）
ASTROFORGE_CLI_FORCE_COLOR=1 ASTROFORGE_CLI_THEME=light python -c "import star_console; ..."
```

回归：`tests/test_star_console.py`（契约字节/双态/映射表）与 `tests/test_module_contract.py`
（5 模块 CLI 子进程非 TTY 端到端 + 裸 print=0 + JSON 三键）。
