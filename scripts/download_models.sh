#!/usr/bin/env bash
# AstroForge 模型下载指引脚本（macOS/Linux）
echo "=== AstroForge model download guide ==="
echo "Option A (ModelScope CLI):"
echo "  pip install modelscope"
echo "  modelscope download --model empero-ai/Qwen3.8-2B-Distill-GGUF qwen3.8-2b-q4_k_m.gguf --local_dir ~/Library/Application\\ Support/AstroForge/models/"
echo "Option B (huggingface-cli):"
echo "  huggingface-cli download empero-ai/Qwen3.8-2B-Distill-GGUF --local-dir models/"
echo ""
echo "Files expected: qwen3.8-2b-q4_k_m.gguf / ornith-9b-q4.gguf"
