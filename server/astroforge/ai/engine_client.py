"""AI 引擎进程客户端（env_ai 独立进程 127.0.0.1:8421，方案 3.7）。

基础设施端点调用（固定配置 base_url，非用户输入 URL，不走外联守卫）；
引擎不可达时统一抛 EngineUnavailable，由路由层转 4004 信封。
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from astroforge.core.config_loader import AiEngineSettings
from astroforge.utils.logger import get_logger

log = get_logger("astroforge.ai")


class EngineUnavailable(RuntimeError):
    pass


class EngineClient:
    def __init__(self, conf: AiEngineSettings):
        self.base_url = conf.base_url.rstrip("/")

    async def health(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/v1/health")
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            raise EngineUnavailable(str(exc)) from exc

    async def infer(self, prompt: str, max_tokens: int = 1024) -> str:
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/infer",
                    json={"prompt": prompt, "max_tokens": max_tokens},
                )
            if resp.status_code != 200:
                raise EngineUnavailable(f"引擎返回 {resp.status_code}: {resp.text[:200]}")
            return resp.json().get("text", "")
        except EngineUnavailable:
            raise
        except Exception as exc:
            raise EngineUnavailable(str(exc)) from exc

    async def model_load(self, model_key: str) -> dict[str, Any]:
        """加载指定模型（热切换，2B↔9B；首次加载耗时较长）。"""
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(
                    f"{self.base_url}/v1/model/load", json={"model_key": model_key}
                )
            if resp.status_code != 200:
                raise EngineUnavailable(f"模型加载失败 {resp.status_code}: {resp.text[:200]}")
            return resp.json()
        except EngineUnavailable:
            raise
        except Exception as exc:
            raise EngineUnavailable(str(exc)) from exc

    async def model_unload(self) -> dict[str, Any]:
        """卸载当前模型释放内存（方案 2.4 机制 4）。"""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(f"{self.base_url}/v1/model/unload")
            return resp.json()
        except Exception as exc:
            raise EngineUnavailable(str(exc)) from exc

    async def infer_stream(self, prompt: str, max_tokens: int = 1024) -> AsyncIterator[str]:
        """SSE 流式推理：逐 data: 行 yield 文本增量。"""
        try:
            client = httpx.AsyncClient(timeout=None)
            req = client.build_request(
                "POST", f"{self.base_url}/v1/infer_stream",
                json={"prompt": prompt, "max_tokens": max_tokens},
            )
            resp = await client.send(req, stream=True)
            resp.raise_for_status()
        except EngineUnavailable:
            raise
        except Exception as exc:
            raise EngineUnavailable(str(exc)) from exc

        async def _stream() -> AsyncIterator[str]:
            try:
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[len("data:"):].strip()
                    if payload in {"", "[DONE]"}:
                        continue
                    try:
                        chunk = json.loads(payload)
                        text = chunk.get("text", "")
                    except json.JSONDecodeError:
                        text = payload
                    if text:
                        yield text
            finally:
                await resp.aclose()
                await client.aclose()

        return _stream()
