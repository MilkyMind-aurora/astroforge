# 根 tests 目录

当前承载**仓库级安全守卫**：

- `test_sql_injection_guard.py`：全仓扫描 Python 源码，禁止字符串拼接/f-string/format 组装 SQL（方案 8.4 硬性条款）。CI 与本地均可独立运行：`python tests/test_sql_injection_guard.py`

各功能模块与服务的单元测试分布：

- `server/tests/`：服务核心（配置/URL 守卫/指令解析/API 冒烟）
- `tests/`：随 Phase 推进迁入模块级集成测试（spider/mineru/md2docx 端到端）
