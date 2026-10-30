#!/bin/bash
# NPU(RKLLM) 번역 서버를 8080 포트에 띄운다 (OpenAI 호환 API: /v1/chat/completions).
# 사용: ./scripts/run_rkllm_server.sh /path/to/model.rkllm      (사전 설치: pip install flask)
set -e
MODEL=${1:?"사용: $0 /path/to/model.rkllm"}
MODEL=$(realpath "$MODEL")
cd "$(dirname "$0")/../rkllm_server"          # flask_server.py 가 lib/librkllmrt.so 를 상대경로로 읽는다
RKLLM_LOG_LEVEL=1 exec python3 flask_server.py --rkllm_model_path "$MODEL" --target_platform rk3588
