"""测试夹具：临时配置目录 + 测试应用（不依赖真实 PostgreSQL）。"""
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture()
def tmp_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """生成指向临时目录的 settings.yaml；数据库密码走环境变量。"""
    monkeypatch.setenv("ASTROFORGE_PG_PASSWORD", "test-pass")
    monkeypatch.setenv("ASTROFORGE_DATA_DIR", str(tmp_path / "data"))
    config = tmp_path / "settings.yaml"
    config.write_text(
        f"""
service:
  host: "127.0.0.1"
  port: 18420
  token_file: "{(tmp_path / "data" / "service_token").as_posix()}"
  auto_upgrade_db: false
database:
  host: "127.0.0.1"
  port: 5432
  db_name: "astroforge_test"
  db_user: "astroforge"
  password_env: "ASTROFORGE_PG_PASSWORD"
system:
  data_dir: "{(tmp_path / "data").as_posix()}"
md2docx:
  template_dir: "{(tmp_path / "templates").as_posix()}"
platform_overrides:
  windows:
    system.data_dir: "{(tmp_path / "data_win").as_posix()}"
  macos:
    system.data_dir: "{(tmp_path / "data_mac").as_posix()}"
""",
        encoding="utf-8",
    )
    yield config
