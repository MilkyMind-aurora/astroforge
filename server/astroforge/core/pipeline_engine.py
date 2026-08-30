"""NovaFlow 流水线引擎：YAML 模板加载/校验/步骤展开（方案 3.5）。

模板驻内存 + 内置播种 + pipelines 表持久化（DB 优先，内存降级）；
步骤级断点续跑完整版属 Phase 5 后续。
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

import yaml

from astroforge.api.response import ApiError, ErrorCode
from astroforge.core.config_loader import REPO_ROOT
from astroforge.utils.logger import get_logger

log = get_logger("astroforge.novaflow")

PIPELINES_DIR = REPO_ROOT / "config" / "pipelines"
VALID_MODULES = {"spider", "mineru", "wpd", "anydoc", "md2docx"}


@dataclass
class StepDef:
    name: str
    module: str
    task_type: str
    config: dict[str, Any] = field(default_factory=dict)
    optional: bool = False


@dataclass
class PipelineDef:
    name: str
    title: str
    description: str
    version: int
    steps: list[StepDef]
    yaml_content: str
    is_builtin: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name, "title": self.title, "description": self.description,
            "version": self.version, "is_builtin": self.is_builtin,
            "steps": [{"name": s.name, "module": s.module, "task_type": s.task_type,
                       "config": s.config, "optional": s.optional} for s in self.steps],
        }


class PipelineEngine:
    def __init__(self) -> None:
        self._pipelines: dict[str, PipelineDef] = {}

    def seed_builtin(self) -> int:
        """启动时播种 config/pipelines/*.yaml；同名自定义模板不覆盖。"""
        count = 0
        if not PIPELINES_DIR.exists():
            log.warning("流水线目录不存在: %s", PIPELINES_DIR)
            return 0
        for path in sorted(PIPELINES_DIR.glob("*.yaml")):
            try:
                parsed = self.parse_yaml(path.read_text(encoding="utf-8"))
                parsed.is_builtin = True
                self._pipelines.setdefault(parsed.name, parsed)
                count += 1
            except ApiError as exc:
                log.error("内置流水线 %s 校验失败: %s", path.name, exc.message)
        log.info("NovaFlow 内置流水线播种完成: %d 条", count)
        return count

    async def sync_db(self) -> int:
        """启动同步（Phase 5.1.5）：加载 DB 自定义模板；内置模板缺失行回写。"""
        try:
            from astroforge.db import engine as db_engine
            from astroforge.db.repositories.tasks import PipelinesRepo

            async with db_engine.get_sessionmaker()() as session:  # type: ignore[misc]
                repo = PipelinesRepo(session)
                rows = await repo.list_all()
                known = {r.name for r in rows}
                loaded = 0
                for row in rows:
                    if row.name in self._pipelines:
                        continue
                    try:
                        parsed = self.parse_yaml(row.yaml_content)
                        parsed.is_builtin = row.is_builtin
                        self._pipelines.setdefault(parsed.name, parsed)
                        loaded += 1
                    except ApiError:
                        log.warning("DB 流水线 %s 校验失败，跳过", row.name)
                for name, pipeline in self._pipelines.items():
                    if pipeline.is_builtin and name not in known:
                        await repo.upsert(
                            name, pipeline.description, True,
                            pipeline.version, pipeline.yaml_content,
                        )
            log.info("NovaFlow DB 同步完成：加载自定义 %d 条", loaded)
            return loaded
        except Exception as exc:
            log.warning("流水线 DB 同步失败（仅内存态）: %s", exc)
            return 0

    def parse_yaml(self, content: str) -> PipelineDef:
        """解析并校验 YAML；失败抛 ApiError(1004)。"""
        try:
            payload = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ApiError(ErrorCode.YAML_INVALID, f"YAML 解析失败: {exc}") from exc
        if not isinstance(payload, dict):
            raise ApiError(ErrorCode.YAML_INVALID, "流水线 YAML 必须是键值映射")
        name = payload.get("name")
        steps = payload.get("steps")
        if not name or not isinstance(name, str):
            raise ApiError(ErrorCode.YAML_INVALID, "缺少 name 字段")
        if not isinstance(steps, list) or not steps:
            raise ApiError(ErrorCode.YAML_INVALID, "steps 必须是非空数组")
        parsed_steps: list[StepDef] = []
        for i, raw in enumerate(steps):
            if not isinstance(raw, dict) or not raw.get("name") or not raw.get("task_type"):
                raise ApiError(ErrorCode.YAML_INVALID, f"steps[{i}] 缺少 name/task_type")
            module = raw.get("module", raw["task_type"].split("_")[0])
            if module not in VALID_MODULES:
                raise ApiError(ErrorCode.YAML_INVALID, f"steps[{i}] 未知 module: {module}")
            parsed_steps.append(StepDef(
                name=str(raw["name"]), module=str(module),
                task_type=str(raw["task_type"]),
                config=raw.get("config") or {}, optional=bool(raw.get("optional", False)),
            ))
        return PipelineDef(
            name=name, title=str(payload.get("title", name)),
            description=str(payload.get("description", "")),
            version=int(payload.get("version", 1)),
            steps=parsed_steps, yaml_content=content,
        )

    def save_custom(self, content: str) -> PipelineDef:
        parsed = self.parse_yaml(content)
        parsed.is_builtin = False
        existing = self._pipelines.get(parsed.name)
        if existing is not None and existing.is_builtin:
            raise ApiError(ErrorCode.YAML_INVALID, f"名称与内置模板冲突: {parsed.name}")
        self._pipelines[parsed.name] = parsed
        # 持久化到 pipelines 表（尽力；DB 不可用时保留内存态，重启前有效）
        asyncio.get_running_loop().create_task(self._db_upsert(parsed))
        return parsed

    async def _db_upsert(self, parsed: PipelineDef) -> None:
        try:
            from astroforge.db import engine as db_engine
            from astroforge.db.repositories.tasks import PipelinesRepo

            async with db_engine.get_sessionmaker()() as session:  # type: ignore[misc]
                repo = PipelinesRepo(session)
                await repo.upsert(
                    parsed.name, parsed.description, False,
                    parsed.version, parsed.yaml_content,
                )
        except Exception as exc:
            log.warning("流水线落库失败（保留内存态）: %s", exc)

    def get(self, name: str) -> PipelineDef | None:
        return self._pipelines.get(name)

    def all(self) -> list[PipelineDef]:
        return list(self._pipelines.values())
