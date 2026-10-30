# translator-kit: 음성 → 한국어 텍스트 → 영어 번역 → 웹

ODROID-M2(RK3588S)에서 **모델만 바꿔 가며** 실시간 번역 파이프라인을 테스트하는 최소 코드입니다.
코드는 `app.py` 하나(약 100줄)입니다.

```
음성(wav 파일 / RTSP)
   └ ffmpeg ─→ VAD(말하는 구간 자르기) ─→ STT(한국어 텍스트) ─→ 번역(영어) ─→ 웹페이지(:8000)
```

| 단계 | 기본값 | 바꾸는 방법 |
|---|---|---|
| STT | SenseVoice (CPU) | `STT_ENGINE=whisper STT_MODEL=small` 등 |
| 번역 | OpenAI 호환 서버 (`TRANSLATE_URL`) | 주소만 바꾸면 NPU 서버, llama.cpp 서버 등으로 교체 |

## 1. 준비물
- ODROID-M2 (또는 Python 3.10+ 와 ffmpeg 가 있는 Linux), `sudo apt install ffmpeg python3-venv`
- NPU 번역을 쓰려면: NPU 드라이버 0.9.x 이상, 변환된 `.rkllm` 모델 (아래 3-A 참고)

## 2. 설치
```bash
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt
./scripts/download_models.sh        # SenseVoice 를 models/ 에 받음
```
Whisper 를 쓰지 않으면 `requirements.txt` 의 `faster-whisper` 줄은 빼도 됩니다.

## 3. 번역 서버 준비 (둘 중 하나)
`app.py` 는 `TRANSLATE_URL` 로 OpenAI 호환 `/v1/chat/completions` 를 호출합니다.

**A. NPU (RKLLM)**
```bash
pip install flask
./scripts/run_rkllm_server.sh /path/to/model.rkllm      # 8080 포트
```
서버 코드와 런타임 라이브러리(`rkllm_server/`: `flask_server.py`, `lib/librkllmrt.so`)는 Rockchip의 [rknn-llm](https://github.com/airockchip/rknn-llm) v1.3.1에서 가져와 동봉했습니다(aarch64 전용, 라이선스는 `rkllm_server/LICENSE`).
`.rkllm` 모델은 보드에서 변환할 수 없습니다. x86 PC 에서 Rockchip 의 [rknn-llm](https://github.com/airockchip/rknn-llm) RKLLM-Toolkit 으로 변환한 뒤 `scp` 로 보드에 복사하세요.
동봉한 런타임은 v1.3.1 입니다. 모델을 변환한 toolkit 이 이보다 높으면 로딩 시 오류가 납니다.

**`.rkllm` 모델 구하는 곳** (RK3588 용, `w8a8` 권장)
1. **Rockchip 공식 model zoo** (변환된 모델 모음): <https://console.box.lenovo.com/l/l0tXb8> , 추출 코드 `rkllm` (rknn-llm README 에 안내된 링크)
2. **Hugging Face 커뮤니티 모델** (예, 모두 Apache-2.0, RK3588 폴더/파일 사용):
   - [`HanzoHuang/Qwen2.5-3B-Instruct-RKLLM`](https://huggingface.co/HanzoHuang/Qwen2.5-3B-Instruct-RKLLM) → `RK3588/Qwen2.5-3B-Instruct_RK3588_w8a8.rkllm` (약 3.5GB)
   - [`HanzoHuang/Qwen2.5-1.5B-Instruct-RKLLM`](https://huggingface.co/HanzoHuang/Qwen2.5-1.5B-Instruct-RKLLM) → `RK3588/Qwen2.5-1.5B-Instruct_RK3588_w8a8.rkllm` (약 1.9GB)
   - [`t-firefly/qwen3-4b-rkllm-rk3588`](https://huggingface.co/t-firefly/qwen3-4b-rkllm-rk3588) → `qwen3-4b_w8a8_rk3588.rkllm` (약 4.6GB)
   ```bash
   pip install -U huggingface_hub
   hf download HanzoHuang/Qwen2.5-3B-Instruct-RKLLM RK3588/Qwen2.5-3B-Instruct_RK3588_w8a8.rkllm --local-dir ./rkllm-models
   ```
   (구버전 huggingface_hub 에서는 `hf` 대신 `huggingface-cli download` 를 씁니다.)
3. 직접 변환: x86 PC 에서 RKLLM-Toolkit 으로 (위 설명 참고)

주의
- 목록에는 SoC 별(`RK3576`, `RK3588`) 파일이 섞여 있으므로 **RK3588** 파일을 받으세요.
- 커뮤니티 모델은 저희가 이 킷으로 **직접 실행해 보지 않았습니다.** 모델 카드 기준으로 위 Qwen2.5 두 개는 RKLLM-Toolkit 1.2.3 으로 변환되었고, 동봉한 런타임(1.3.1)보다 낮은 버전이라 로딩될 가능성이 높지만 확인은 필요합니다.
- 메모리: 저희 측정으로 Qwen2.5-3B(w8a8)는 NPU 서버가 피크 약 3.4GB, 1.5B 는 약 1.8GB 였습니다(서버 로그의 `Peak Memory Usage`). 8GB 보드에서 STT, 데스크톱 환경과 함께 쓸 때 여유를 확인하세요.
- **번역 품질은 모델마다 다릅니다.** 특히 작은 모델(1.5B급)은 한국어를 영어로 옮길 때 한글을 그대로 출력하거나 오역하는 일이 있습니다. 영→한 번역은 이 킷에서 아직 지원하지 않습니다.

**B. CPU (llama.cpp)**
`llama-server -m model.gguf --port 8080` 처럼 띄우면 같은 주소로 쓸 수 있습니다.

## 4. 실행
```bash
python app.py test.wav              # 음성 파일 (실시간 속도로 재생)
python app.py rtsp://<주소>          # RTSP
# 브라우저: http://<보드IP>:8000
```
빅코어(4~7번)에 고정하면 CPU 경쟁이 줄어듭니다: `taskset -c 4-7 python app.py test.wav`

## 5. 설정 (환경변수)
| 변수 | 기본값 | 설명 |
|---|---|---|
| `STT_ENGINE` | `sensevoice` | `sensevoice` 또는 `whisper` |
| `STT_MODEL` | `small` | Whisper 모델 (`tiny` `base` `small` `medium` `large-v3-turbo`) |
| `SENSEVOICE_DIR` | `models/sherpa-onnx-...-2024-07-17` | SenseVoice 모델 폴더 |
| `TRANSLATE_URL` | `http://127.0.0.1:8080/v1/chat/completions` | 번역 서버 주소 |
| `PORT` | `8000` | 웹 포트 |

예: `STT_ENGINE=whisper STT_MODEL=base TRANSLATE_URL=http://192.168.0.5:8080/v1/chat/completions python app.py test.wav`

구간 자르기 값(0.5초 무음, 6초 상한)은 `app.py` 의 `listen()` 안에 있습니다(`silence >= 25`, `len(speech) >= 300`, 20ms 단위).

## 6. 직접 모델을 바꿔 보려면
- **STT**: `app.py` 의 `stt(audio)` 함수 하나만 구현하면 됩니다. `audio` 는 16kHz mono float32 numpy 배열, 반환은 문자열.
- **번역**: `translate(ko)` 함수 하나. 반환은 문자열.

## 7. 알려진 제한 (꼭 읽어 주세요)
- **한국어 → 영어 한 방향만 구현**되어 있습니다. 영→한, 한영 혼용 세션(언어 자동 판별)은 아직 없습니다. SenseVoice 는 결과에 언어 태그(`<|ko|>`, `<|en|>`)를 주지만 코드에서 쓰지 않습니다.
- **RTSP 는 아직 테스트하지 못했습니다.** 파일 입력으로만 검증했습니다.
- 말 구간을 **최대 6초**로 자르므로 긴 문장이 중간에서 끊겨 STT, 번역 품질이 떨어질 수 있습니다.
- RKLLM 서버(`flask_server.py`)는 `system` 메시지를 모델에 전달하지 않는 것으로 보여서, 번역 지시를 **user 메시지 안에** 넣었습니다(`translate()` 참고).
- 번역 모델이 작으면(1.5B급) 한글이 그대로 출력되거나 오역이 있습니다. 모델 크기와 품질은 직접 확인하세요.
- SenseVoice **2025-09 버전은 테스트 환경(sherpa-onnx 2.0.1)에서 한국어 출력이 깨져서** 2024-07 버전을 씁니다. 원인은 확인하지 못했습니다.
- Whisper 의 `medium`, `large-v3-turbo` 는 말 구간 단위로 쓰기엔 느립니다(구간 하나당 처리 시간이 구간 길이보다 길 수 있음).
- 웹 서버(8000)와 `flask_server.py`(8080)는 **인증 없이 모든 인터페이스(0.0.0.0)에 열립니다.** 신뢰할 수 있는 네트워크에서만 쓰세요.
- 결과 목록(`results`)이 메모리에 계속 쌓입니다. 장시간 연속 실행에는 정리 로직이 필요합니다.
