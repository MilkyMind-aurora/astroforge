"""配置加载与平台覆盖合并测试（方案 2.4 机制 2）。"""
from __future__ import annotations

import sys
from pathlib import Path

from astroforge.core.config_loader import Settings, load_settings


def test_load_defaults_without_file(tmp_path: Path):
    settings = load_settings(tmp_path / "nonexistent.yaml")
    assert settings.service.port == 8420
    assert settings.ai_engine.base_url == "http://127.0.0.1:8421"


def test_platform_override_merges(tmp_settings: Path, monkeypatch):
    """平台覆盖段按点分键覆盖全局值（本机平台分支）。"""
    monkeypatch.setattr(sys, "platform", "win32")
    settings = load_settings(tmp_settings)
    assert "data_win" in settings.system.data_dir
    monkeypatch.setattr(sys, "platform", "darwin")
    settings = load_settings(tmp_settings)
    assert "data_mac" in settings.system.data_dir


def test_password_from_env_only(tmp_settings: Path):
    settings = load_settings(tmp_settings)
    assert settings.database.password() == "test-pass"


def test_password_env_missing_raises(tmp_settings: Path, monkeypatch):
    monkeypatch.delenv("ASTROFORGE_PG_PASSWORD", raising=False)
    settings = load_settings(tmp_settings)
    import pytest

    with pytest.raises(RuntimeError):
        settings.database.password()


def test_dotted_override_conflict_raises(tmp_path: Path, monkeypatch):
    # 平台覆盖仅在匹配平台上应用；固定 windows 分支使断言与运行平台无关
    monkeypatch.setattr(sys, "platform", "win32")
    config = tmp_path / "s.yaml"
    config.write_text(
        """
system:
  data_dir: "./data/"
  task_concurrency: 1
platform_overrides:
  windows:
    system.data_dir.nested: "x"
""",
        encoding="utf-8",
    )
    import pytest

    with pytest.raises((ValueError, Exception)):
        load_settings(config)


def test_model_defaults():
    s = Settings()
    assert s.monitor.memory_critical_gb == 12
    assert s.ai.instruction.max_retry == 2
