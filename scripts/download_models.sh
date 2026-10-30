#!/bin/bash
# SenseVoice(한/영/중/일/광둥어 STT) 모델을 models/ 에 받는다.
# 2025-09 버전은 테스트한 환경(sherpa-onnx 2.0.1)에서 한국어가 깨져서 2024-07 버전을 쓴다.
set -e
cd "$(dirname "$0")/.."
mkdir -p models && cd models
NAME=sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17
[ -d "$NAME" ] && { echo "이미 있음: models/$NAME"; exit 0; }
curl -L -o sv.tar.bz2 "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/$NAME.tar.bz2"
tar xjf sv.tar.bz2 && rm sv.tar.bz2
echo "완료: models/$NAME"
