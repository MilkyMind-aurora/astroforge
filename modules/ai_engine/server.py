"""AI 引擎独立进程（env_ai，127.0.0.1:8421，方案 3.7）。

与 Sidereal Core（8420）进程隔离：模型 OOM/崩溃不拖垮服务核心，
由服务核心 watcher 看护自动重启（≤restart_limit 次）。
模型常驻/闲置 5 分钟卸载/2B↔9B 热切换的完整版属 Phase 6.1。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import threading
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="AstroForge AI Engine", version="0.1.0")

_state = {"model_key": None, "model": None, "last_used": 0.0}
_lock = threading.Lock()

# 模型清单与路径来源：环境变量 ASTROFORGE_MODEL_DIR（默认 ./models）
# qwen2b 即方案指定的 empero-ai/Qwen3.8-2B-Distill（HF，经 hf-mirror 下载）
MODEL_FILES = {
    "qwen2b": "Qwen3.8-2B-Q4_K_M.gguf",
    "ornith9b": "ornith-9b-q4.gguf",
}
# 闲置自动卸载（方案 2.4 机制 4 / 3.7 动态内存管理；秒）
IDLE_TIMEOUT = int(os.environ.get("ASTROFORGE_IDLE_TIMEOUT", "300"))


def _model_dir() -> Path:
    return Path(os.environ.get("ASTROFORGE_MODEL_DIR", "./models"))


@app.on_event("startup")
async def _start_idle_watcher() -> None:
    """闲置看护：模型加载后超过 IDLE_TIMEOUT 未使用即自动卸载（Phase 6.1.5）。"""
    async def _watch() -> None:
        while True:
            await asyncio.sleep(30)
            with _lock:
                loaded = _state["model"] is not None
            if loaded and time.time() - _state["last_used"] > IDLE_TIMEOUT:
                with _lock:
                    _state["model"] = None
                    _state["model_key"] = None
                print(f"[INFO] 模型闲置超过 {IDLE_TIMEOUT}s，已自动卸载释放内存", flush=True)
    asyncio.create_task(_watch())


def _load_model(model_key: str):
    try:
        from llama_cpp import Llama
    except ImportError:
        raise HTTPException(status_code=503, detail={"code": 3005, "message": "llama-cpp-python 未安装"})
    path = _model_dir() / MODEL_FILES[model_key]
    if not path.exists():
        raise HTTPException(status_code=503, detail={"code": 3005, "message": f"模型文件缺失: {path}"})
    return Llama(model_path=str(path), n_ctx=4096, verbose=False)


class InferBody(BaseModel):
    prompt: str
    max_tokens: int = 1024


class ModelBody(BaseModel):
    model_key: str


@app.get("/v1/health")
async def health():
    return {"ok": True, "model_loaded": _state["model"] is not None, "current_model": _state["model_key"]}


def _system_prompt() -> str:
    """系统提示词：env ASTROFORGE_SYSTEM_PROMPT 指定路径（方案 3.7 行为边界）。"""
    default = Path(__file__).resolve().parents[2] / "config" / "ai_system_prompt.txt"
    path = Path(os.environ.get("ASTROFORGE_SYSTEM_PROMPT", str(default)))
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return "你是 AstroForge 的 AI 副驾驶，负责把用户意图解析为结构化任务指令。"


def _chat(messages: list[dict], max_tokens: int, stream: bool = False):
    """Chat 模板补全（裸补全会复述提示词，指令准确率骤降）。"""
    return _state["model"].create_chat_completion(
        messages=[{"role": "system", "content": _system_prompt()},
                  {"role": "user", "content": messages}],
        max_tokens=max_tokens, stream=stream,
    )


@app.post("/v1/model/load")
async def load_model(body: ModelBody):
    if body.model_key not in MODEL_FILES:
        raise HTTPException(status_code=400, detail={"code": 1001, "message": f"未知模型: {body.model_key}"})
    with _lock:
        _state["model"] = _load_model(body.model_key)
        _state["model_key"] = body.model_key
        _state["last_used"] = time.time()  # 重置闲置计时，防止 load 后立即被看护卸载
    return {"ok": True, "current_model": body.model_key}


@app.post("/v1/model/unload")
async def unload_model():
    with _lock:
        _state["model"], _state["model_key"] = None, None  # 释放内存（方案 2.4 机制 4）
    return {"ok": True, "current_model": None}


@app.post("/v1/model/switch")
async def switch_model(body: ModelBody):
    with _lock:
        _state["model"] = _load_model(body.model_key)
        _state["model_key"] = body.model_key
        _state["last_used"] = time.time()  # 重置闲置计时
    return {"ok": True, "current_model": body.model_key}


@app.post("/v1/infer")
async def infer(body: InferBody):
    if _state["model"] is None:
        raise HTTPException(status_code=503, detail={"code": 3005, "message": "模型未加载"})
    _state["last_used"] = time.time()
    with _lock:
        output = _chat(body.prompt, body.max_tokens)
    return {"text": output["choices"][0]["message"]["content"]}


@app.post("/v1/infer_stream")
async def infer_stream(body: InferBody):
    if _state["model"] is None:
        raise HTTPException(status_code=503, detail={"code": 3005, "message": "模型未加载"})
    _state["last_used"] = time.time()

    async def _sse():
        stream = _chat(body.prompt, body.max_tokens, stream=True)
        for chunk in stream:
            choice = chunk["choices"][0]
            token = choice.get("text") or (choice.get("delta") or {}).get("content", "")
            if token:
                yield f"data: {json.dumps({'text': token}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(_sse(), media_type="text/event-stream")


def main() -> None:
    parser = argparse.ArgumentParser(description="AstroForge AI 引擎进程")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8421)
    args = parser.parse_args()
    import uvicorn

    uvicorn.run(app, host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
