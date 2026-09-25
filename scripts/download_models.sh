#!/usr/bin/env bash
# AstroForge model download guide (no real download; print commands for user)
# Primary model: empero-ai/Qwen3.8-2B-Distill-GGUF (HuggingFace, use hf-mirror in CN)
# 星幕输出（MF3）：横幅经 star_console；python 缺失时静默跳过
python3 "$(dirname "$0")/../modules/_shared/star_console.py" banner download_models "GGUF model download guide" 2>/dev/null || true
echo "=== AstroForge model download guide ==="
echo "Option A (hf-mirror direct, recommended in CN):"
echo "  curl -L -o models/Qwen3.8-2B-Q4_K_M.gguf https://hf-mirror.com/empero-ai/Qwen3.8-2B-Distill-GGUF/resolve/main/Qwen3.8-2B-Q4_K_M.gguf"
echo "Option B (huggingface-cli with mirror endpoint):"
echo "  HF_ENDPOINT=https://hf-mirror.com huggingface-cli download empero-ai/Qwen3.8-2B-Distill-GGUF Qwen3.8-2B-Q4_K_M.gguf --local-dir models/"
echo "Option C (ModelScope fallback, equivalent spec):"
echo "  modelscope download --model Qwen/Qwen2.5-1.5B-Instruct-GGUF qwen2.5-1.5b-instruct-q4_k_m.gguf --local_dir models/"
echo ""
echo "File expected: Qwen3.8-2B-Q4_K_M.gguf (macOS: ~/Library/Application Support/AstroForge/models/)"
