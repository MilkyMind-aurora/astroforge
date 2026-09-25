# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，版本号语义化（SemVer）。

## [Unreleased]

> 服务核心 Sidereal Core（REST 26 路由 + 3 WS 通道 + PostgreSQL 双写）、五大模块 CLI、
> NovaFlow 流水线、AI 引擎独立进程（llama.cpp + GGUF）、端到端冒烟矩阵与 Windows 打包
> 均已随 Phase 1-8 落在主干；下列为本轮「前端优化方案 V1-星空版」里程碑（MF0-MF6）交付。

### Added（星空版前端）
- 星空设计系统基建（MF0）：`config/design/tokens.yaml` 唯一事实源（含 WCAG 取证修正值）+
  icons.yaml 星符表 + quotes.yaml 台词库 + deep-space/dawn 双主题包；`scripts/gen_design.py`
  三端渲染器（TUI tokens.tcss/tokens.py · Flutter tokens.g.dart · CLI star_console 生成段 +
  星野种子）；`scripts/ui_doctor.py` 聚合验收与 CI 设计契约门禁（改 token 不重新生成即红灯）
- TUI 星舰工作台（MF1/MF2）：页面插件化（entry_points + pages.yaml）、星轨侧栏与状态栏、
  监控看板、业务页全量真实化（占位页清零）、星伴 AI 抽屉（流式合批/思考帧/指令卡）、
  日志面板与命令面板
- CLI 星幕渲染器（MF3）：star_console 六件套（banner/stage/progress/result_card/error_card/log）
  + 错误码修复指引映射，5 模块 CLI 与脚本接线，TTY/非 TTY 双态降级（stdout 契约字节不变）
- 步骤级断点续跑 API（MF3.5）：`POST /tasks/{uuid}/steps/{index}/retry`（原地更新不裂变）
- Flutter 星空版（MF4/MF5）：Kimi 式桌面壳层（72dp 图标轨/星野 fragment shader/星仔星球引擎/
  触点圆形扩散主题切换）、首页对话式入口（引擎休眠降级+拖拽建任务+纯键盘流）、任务/流水线/
  历史/设置页、监控降级右上仪表胶囊+星象台弹层、AI 抽屉与模型弹层
- MF6 收口：双主题冻结帧截图 10 张（`docs/design/screenshots/`，golden test uTime=0）、
  动效 26 项勾账表（`docs/design/motion-checkoff.md`）、ui_doctor --full 全绿

### Changed
- Flutter IA 8 页 → 5 页（UX 评审总裁决）：采集/解析/转换三合一「任务」页，
  监控降级为右上仪表胶囊+弹层；TUI 保留 8 页，双端数据互通+术语一致
- 设计取值纪律：三端禁止 tokens.yaml 之外的硬编码色值与星符（CI grep 断言）

## [0.1.0] - 2026-08-31

### Added
- 项目骨架与工程化基线：monorepo 目录、CI（GitHub Actions 双平台）、配置体系
- 命名体系定稿：AstroForge / Sidereal Core / NovaFlow
- 内置流水线 YAML 模板 ×4（学术论文 / 官方文档采集 / 办公批量 / 数模数据）
- SQL 参数绑定静态守卫测试（仓库级安全门禁）

[Unreleased]: https://github.com/MilkyMind-aurora/astroforge/compare/0.1.0...HEAD
[0.1.0]: https://github.com/MilkyMind-aurora/astroforge/releases/tag/0.1.0
