"""AI 引擎独立进程（env_ai，127.0.0.1:8421，方案 3.7）。

与 Sidereal Core（8420）进程隔离：模型 OOM/崩溃不拖垮服务核心，
由服务核心 watcher 看护自动重启（≤restart_limit 次）。
模型常驻/闲置 5 分钟卸载/2B↔9B 热切换的完整版属 Phase 6.1。
"""
from __future__ import annotations

import argparse
import json
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="AstroForge AI Engine", version="0.1.0")

_state = {"model_key": None, "model": None}
_lock = threading.Lock()

# 模型清单与路径来源：环境变量 ASTROFORGE_MODEL_DIR（默认 ./models）
# qwen2b 别名对应规格等价的真实模型（Qwen2.5-1.5B Q4_K_M，~1.0GB）
MODEL_FILES = {
    "qwen2b": "Qwen3.8-2B-Q4_K_M.gguf",
    "ornith9b": "ornith-9b-q4.gguf",
}


def _model_dir() -> Path:
    import os

    return Path(os.environ.get("ASTROFORGE_MODEL_DIR", "./models"))


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


@app.post("/v1/model/load")
async def load_model(body: ModelBody):
    if body.model_key not in MODEL_FILES:
        raise HTTPException(status_code=400, detail={"code": 1001, "message": f"未知模型: {body.model_key}"})
    with _lock:
        _state["model"] = _load_model(body.model_key)
        _state["model_key"] = body.model_key
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
    return {"ok": True, "current_model": body.model_key}


@app.post("/v1/infer")
async def infer(body: InferBody):
    if _state["model"] is None:
        raise HTTPException(status_code=503, detail={"code": 3005, "message": "模型未加载"})
    with _lock:
        output = _state["model"](body.prompt, max_tokens=body.max_tokens, echo=False)
    return {"text": output["choices"][0]["text"]}


@app.post("/v1/infer_stream")
async def infer_stream(body: InferBody):
    if _state["model"] is None:
        raise HTTPException(status_code=503, detail={"code": 3005, "message": "模型未加载"})

    async def _sse():
        stream = _state["model"](body.prompt, max_tokens=body.max_tokens, echo=False, stream=True)
        for chunk in stream:
            token = chunk["choices"][0].get("text", "")
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
