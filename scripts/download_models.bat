# -*- coding: utf-8 -*-
# AstroForge 模型下载指引脚本（不做真实下载，打印命令由用户执行）
@echo off
echo === AstroForge model download guide ===
echo Option A (ModelScope CLI):
echo   pip install modelscope
echo   modelscope download --model empero-ai/Qwen3.8-2B-Distill-GGUF qwen3.8-2b-q4_k_m.gguf --local_dir models\
echo   modelscope download --model Ornith-1.5-9B-GGUF ornith-9b-q4.gguf --local_dir models\
echo Option B (huggingface-cli):
echo   huggingface-cli download empero-ai/Qwen3.8-2B-Distill-GGUF --local-dir models\
echo.
echo Files expected by config\settings.yaml:
echo   models\qwen3.8-2b-q4_k_m.gguf
echo   models\ornith-9b-q4.gguf
