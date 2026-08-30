"""SQL 参数绑定静态守卫（硬性安全条款，见方案 8.4）。

扫描仓库内全部 Python 源码，禁止以字符串拼接/f-string/format 方式组装 SQL。
命中即失败，阻断合并。可直接运行：python tests/test_sql_injection_guard.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Windows CI 控制台非 UTF-8 编码，强制统一避免 ✅/❌ 输出崩溃
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist",
    ".codegraph", ".deepsec", ".mimosa", "data",
}

# 危险模式：f-string / format / % 拼接进入 SQL 语境
# text( 前禁止有单词字符/下划线/点（排除 write_text(f 之类误报）
_DANGER_TEXT = r"(?:^|[^\w.])text\(\s*f[\"']"
DANGER_PATTERNS = [
    (re.compile(_DANGER_TEXT), "f-string 传入 text()"),
    (re.compile(r"execute\(\s*f[\"']"), "f-string 直接 execute"),
    (re.compile(r"(executemany|executescript)\(\s*f[\"']"), "f-string 执行脚本"),
]
# 行级模式：同一行内同时出现 SQL 关键字与拼接调用
SQL_KEYWORD = re.compile(r"\b(select|insert|update|delete|create\s+table|alter\s+table)\b", re.IGNORECASE)
CONCAT_CALL = re.compile(r"\.format\(|%\s*\(|\+\s*(str\(|params|request|config|user)")


def iter_py_files(root: Path):
    for path in root.rglob("*.py"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        yield path


def scan() -> list[str]:
    findings: list[str] = []
    for path in iter_py_files(REPO_ROOT):
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        for no, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            for pattern, label in DANGER_PATTERNS:
                if pattern.search(line):
                    findings.append(f"{rel}:{no}: {label}: {stripped[:120]}")
            if SQL_KEYWORD.search(line) and CONCAT_CALL.search(line):
                findings.append(f"{rel}:{no}: SQL 关键字与字符串拼接同行: {stripped[:120]}")
    return findings


def test_no_sql_string_building():
    findings = scan()
    assert not findings, "检测到 SQL 拼接（必须改为参数绑定）:\n" + "\n".join(findings)


if __name__ == "__main__":
    issues = scan()
    if issues:
        print(f"❌ SQL 参数绑定守卫：{len(issues)} 处违规")
        for item in issues:
            print(" -", item)
        sys.exit(1)
    print("✅ SQL 参数绑定守卫：全部源码通过")
