<div align="center">

# 🌟 AstroForge · 衍星台

**Forging Order from Stellar Chaos.** — 星辰混沌中，锻铸秩序。

单入口本地文档智能处理工作台：把原始数据（氢）锻造成高价值文档（重元素）。

[![CI](https://github.com/MilkyMind-aurora/astroforge/actions/workflows/ci.yml/badge.svg)](https://github.com/MilkyMind-aurora/astroforge/actions/workflows/ci.yml)
[![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS-lightgrey.svg)](#双平台安装)

</div>

## 这是什么

AstroForge（衍星台）是一个**单机全栈、离线优先**的本地工作台：

- **爬取**：基于 Scrapling 的自适应网页爬虫（整站文档结构化、PDF 批量下载、表格数据抓取）
- **解析**：MinerU（PDF/图片 → 结构化 Markdown）+ WebPlotDigitizer（图表数值提取）
- **转换**：anydoc（办公文档 → MD，Rust）+ md2docx（MD → Word，5 套场景模板）
- **编排**：NovaFlow 流水线引擎（YAML 模板 + 断点续跑 + AI 自然语言驱动）
- **AI 副驾驶**：本地 GGUF 模型（llama.cpp），自然语言 → 结构化任务指令
- **双 UI**：TUI（Textual，终端沉浸）+ Flutter 桌面端（Windows/macOS 图形界面），数据同源
- **存储**：PostgreSQL 主存储，任务/产物/AI 会话/监控时序全部结构化可回溯

命名体系：**AstroForge**（正式名）· **Sidereal Core**（服务核心守护进程）· **NovaFlow**（流水线引擎）。

## 架构一览

```
TUI（Textual）＋ Flutter 桌面端          ← 双 UI 客户端
        │ REST + WebSocket（127.0.0.1:8420）
Sidereal Core 服务核心（FastAPI）        ← API 网关 / 任务调度 / NovaFlow 流水线 / 监控
        │ conda run 子进程隔离
功能模块层 env_spider · env_mineru · env_wpd · anydoc(Rust) · env_md2docx · env_ai(独立引擎进程 :8421)
        │
PostgreSQL 16 ＋ 本地文件库（raw/output/logs/templates/backups）
```

## Monorepo 布局

| 目录 | 内容 |
| --- | --- |
| `server/` | Sidereal Core 服务核心（Python 包 `astroforge`）：API、调度、监控、持久化 |
| `tui/` | Textual 终端工作台 |
| `app/` | Flutter 桌面端（windows/macos） |
| `modules/` | 五大功能模块 CLI（独立 conda 环境运行）+ AI 引擎进程 |
| `config/` | 全局配置、AI 系统提示词、NovaFlow 内置流水线模板 |
| `templates/` | DOCX 场景模板（学术论文/技术文档/数模/通用/正式报告） |
| `scripts/` | 部署、备份、环境体检脚本 |
| `tests/` | 仓库级安全守卫（SQL 参数绑定静态扫描） |

## 双平台安装

### Windows（开发主战场，开箱即用）

```bat
git clone https://github.com/MilkyMind-aurora/astroforge.git
cd astroforge
scripts\install_remaining_envs.bat   :: 创建 conda 环境与依赖
scripts\db_init.sql                  :: psql 初始化 astroforge 库（或手动执行）
scripts\start_service.bat            :: 启动 Sidereal Core（127.0.0.1:8420）
scripts\start_tui.bat                :: 启动 TUI 工作台
```

依赖前提：Anaconda（或 Miniconda）、PostgreSQL ≥ 16、Rust 工具链（anydoc 编译）、Git。
数据库密码通过环境变量注入：`set ASTROFORGE_PG_PASSWORD=你的密码`（不落明文）。

### macOS（开源用户，核心可编译，重依赖自装）

```bash
git clone https://github.com/MilkyMind-aurora/astroforge.git && cd astroforge
bash scripts/install_check.sh        # 一键体检：conda/PG/浏览器/模型缺失项清单
bash scripts/install_envs_macos.sh   # 创建 conda 环境与依赖
bash scripts/start_service.sh        # nohup 守护启动
bash scripts/start_tui.sh
```

macOS 数据目录规范：`~/Library/Application Support/AstroForge/`（模型、数据、日志统一收口）。

## 当前状态（透明化）

项目按两年里程碑推进，当前处于 **Phase 7-8（集成测试与打包）**：

| 里程碑 | 状态 |
| --- | --- |
| M0 环境验证 / 配置体系 / CI | ✅ 完成（CI 三平台持续绿） |
| M1 服务核心 + TUI + 监控 | ✅ 完成（26 REST 路由 + 3 WS 通道 + 双写 PostgreSQL） |
| M2 爬虫（Vue 官方文档整站结构化实测） | ✅ 完成（9 章节 52 页，断点续爬，Scrapling 渲染） |
| M3 解析（MinerU 真机 ✅ / WPD 精度测试 ✅） | ✅ 完成 |
| M4 转换（anydoc v0.2.4 编译 ✅ / md2docx 5 套模板 ✅） | ✅ 完成 |
| M5 NovaFlow 流水线（模板持久化 + 运行） | ✅ 完成（步骤级断点续跑待做） |
| M6 AI 副驾驶（独立进程/流式/对话入库/闲置卸载） | ✅ 完成（2B↔9B 切换 UI 待做） |
| M7 集成测试与稳定性 | 🚧 冒烟矩阵 7/7 PASS；72h 长稳待跑 |
| M8 Windows 打包 | 🚧 iss 就绪；Flutter 构建需系统开发者模式 |
| M10 Flutter 桌面端（三页真实表单） | ✅ 完成 |
| M11 macOS 适配 + 双平台 CI | 🚧 CI 就绪，实机矩阵待跑 |
| M12 开源正式发布 v1.0 | ⏳ |

## 验证工具

```bash
# 端到端冒烟矩阵（需服务核心运行中；--skip-ai 跳过引擎用例）
python scripts\smoke_e2e.py

# 内存峰值观测（另终端启动被测进程后传入 PID）
python scripts\bench_memory.py --pid <PID> --label "MinerU 解析" --budget-gb 12

# 重新生成 5 套 DOCX 模板
python scripts\make_templates.py

# 打包（Windows：先 flutter build windows --release，再 Inno Setup 编译）
iscc app\packaging\windows\astroforge.iss
# macOS
bash app\packaging\macos\make_dmg.sh
```

完整方案见仓库文档（构建方案 13 章 + 9 个工程补丁）。

## 安全声明

- 所有 SQL 访问强制参数绑定，CI 静态守卫扫描（`tests/test_sql_injection_guard.py`）
- 服务核心仅监听 `127.0.0.1`，本机 token 认证（`X-AstroForge-Token`）
- 除爬虫与首次安装外全部功能离线运行；不向任何第三方上传用户数据
- 对用户提供的 URL 实施外联安全校验（拒绝内网/环回/保留地址的 SSRF 防护仅用于服务自身发起的非爬虫请求；爬虫模块按设计需访问任意目标站）

## License

[Apache-2.0](LICENSE) © MilkyMind-aurora
