"""配置加载与平台覆盖合并（方案 2.4 机制 2 / 5.2）。

合并规则：platform_overrides 中当前平台的点分键覆盖全局值；
路径值统一展开 ~；数据库密码只从环境变量读取，不落明文。
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = REPO_ROOT / "config" / "settings.yaml"


class ServiceSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8420
    token_file: str = "./data/service_token"
    auto_upgrade_db: bool = True
    log_level: str = "INFO"


class DatabaseSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 5432
    db_name: str = "astroforge"
    db_user: str = "astroforge"
    password_env: str = "ASTROFORGE_PG_PASSWORD"
    pool_size: int = 10
    max_overflow: int = 5
    pool_pre_ping: bool = True
    pool_recycle: int = 3600

    def password(self) -> str:
        """密码仅从环境变量读取；缺失时明确报错而非静默降级。"""
        value = os.environ.get(self.password_env, "")
        if not value:
            raise RuntimeError(f"环境变量 {self.password_env} 未设置（数据库密码不落明文）")
        return value


class AiEngineSettings(BaseModel):
    base_url: str = "http://127.0.0.1:8421"
    restart_limit: int = 3


class InstructionSettings(BaseModel):
    max_retry: int = 2
    fallback_keyword_mode: bool = True
    fallback_notice: bool = True


class AiSettings(BaseModel):
    enabled: bool = True
    default_model: str = "qwen2b"
    model_path: dict[str, str] = Field(default_factory=dict)
    n_ctx: int = 4096
    n_threads: int = 4
    idle_unload: bool = True
    idle_timeout: int = 300
    system_prompt: str = "./config/ai_system_prompt.txt"
    instruction: InstructionSettings = InstructionSettings()


class BrowserSettings(BaseModel):
    chromium_path: str = ""
    headless: bool = True
    timeout: int = 30000
    request_interval: float = 1.0
    auto_retry: int = 3
    solve_cloudflare: bool = True
    no_sandbox: bool = True


class MineruSettings(BaseModel):
    model_source: str = "modelscope"
    model_dir: str = ""
    modelscope_cache: str = ""
    backend: str = "pipeline"
    max_threads: int = 4


class Md2DocxSettings(BaseModel):
    template_dir: str = "./templates/"
    default_template: str = "tech_doc"
    enable_toc: bool = True
    enable_page_number: bool = True


class MonitorSettings(BaseModel):
    refresh_interval: int = 1
    aggregate_interval: int = 10
    memory_warning_gb: float = 10
    memory_critical_gb: float = 12
    show_curve: bool = True
    history_hours: int = 24
    jsonl_export: bool = False
    jsonl_dir: str = "./data/monitor/"


class SystemSettings(BaseModel):
    max_memory_gb: float = 12
    task_concurrency: int = 1
    data_dir: str = "./data/"
    mascot_enabled: bool = True


class Settings(BaseModel):
    service: ServiceSettings = ServiceSettings()
    database: DatabaseSettings = DatabaseSettings()
    ai_engine: AiEngineSettings = AiEngineSettings()
    ai: AiSettings = AiSettings()
    browser: BrowserSettings = BrowserSettings()
    mineru: MineruSettings = MineruSettings()
    md2docx: Md2DocxSettings = Md2DocxSettings()
    monitor: MonitorSettings = MonitorSettings()
    system: SystemSettings = SystemSettings()
    config_path: str = ""

    # ---- 常用派生路径（均已展开 ~ 与相对锚点）----
    def _anchor(self, value: str) -> Path:
        path = Path(os.path.expanduser(value))
        return path if path.is_absolute() else (REPO_ROOT / path).resolve()

    def data_dir(self) -> Path:
        return self._anchor(self.system.data_dir)

    def token_file(self) -> Path:
        return self._anchor(self.service.token_file)

    def template_dir(self) -> Path:
        return self._anchor(self.md2docx.template_dir)

    def logs_dir(self) -> Path:
        return self.data_dir() / "logs"


def _platform_key() -> str | None:
    if sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return None


def _set_dotted(data: dict[str, Any], dotted: str, value: Any) -> None:
    """把 "a.b.c" 点分键写入嵌套 dict。"""
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise ValueError(f"platform_overrides 键冲突: {dotted}")
    node[parts[-1]] = value


def _expanduser_deep(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("~"):
        return os.path.expanduser(value)
    if isinstance(value, dict):
        return {k: _expanduser_deep(v) for k, v in value.items()}
    return value


def load_settings(config_path: str | Path | None = None) -> Settings:
    path = Path(config_path or os.environ.get("ASTROFORGE_CONFIG") or DEFAULT_CONFIG)
    raw: dict[str, Any] = {}
    if path.exists():
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    overrides = raw.pop("platform_overrides", {}) or {}
    platform = _platform_key()
    if platform and platform in overrides:
        for dotted, value in (overrides[platform] or {}).items():
            _set_dotted(raw, dotted, _expanduser_deep(value))
    settings = Settings(**raw)
    settings.config_path = str(path)
    return settings


_cache: dict[str, Settings] = {}
_lock = threading.Lock()


def get_settings() -> Settings:
    """进程级缓存的配置单例；热更新走 reload_settings()。"""
    with _lock:
        if "settings" not in _cache:
            _cache["settings"] = load_settings()
        return _cache["settings"]


def reload_settings() -> Settings:
    with _lock:
        _cache["settings"] = load_settings()
        return _cache["settings"]
