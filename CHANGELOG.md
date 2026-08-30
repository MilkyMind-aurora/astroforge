# Changelog

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/) 规范，版本号语义化（SemVer）。

## [Unreleased]

### 计划中（Phase 0-1 冲刺）
- 服务核心 Sidereal Core：REST + WebSocket API、PostgreSQL 持久化、任务调度
- TUI 工作台（Textual）与 Flutter 桌面端（Windows/macOS）
- 五大功能模块 CLI：spider / mineru / wpd / anydoc / md2docx
- AI 引擎独立进程（llama.cpp + GGUF）

## [0.1.0] - 2026-08-31

### Added
- 项目骨架与工程化基线：monorepo 目录、CI（GitHub Actions 双平台）、配置体系
- 命名体系定稿：AstroForge / Sidereal Core / NovaFlow
- 内置流水线 YAML 模板 ×4（学术论文 / 官方文档采集 / 办公批量 / 数模数据）
- SQL 参数绑定静态守卫测试（仓库级安全门禁）

[Unreleased]: https://github.com/MilkyMind-aurora/astroforge/compare/0.1.0...HEAD
[0.1.0]: https://github.com/MilkyMind-aurora/astroforge/releases/tag/0.1.0
