"""음성(파일 또는 RTSP) → 한국어 텍스트(STT) → 영어(번역) → 웹페이지
실행:  python app.py [파일 또는 rtsp 주소]      브라우저: http://보드IP:8000
설정: README.md 참고 (STT_ENGINE, STT_MODEL, TRANSLATE_URL, PORT 환경변수)
"""
import json, os, subprocess, sys, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import numpy as np
import webrtcvad

# ── 설정: 환경변수로 바꾸거나 여기 값을 직접 수정 ────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = sys.argv[1] if len(sys.argv) > 1 else "test.wav"          # 파일 경로 또는 "rtsp://..."
STT_ENGINE = os.environ.get("STT_ENGINE", "sensevoice")             # "sensevoice"(빠름) 또는 "whisper"
STT_MODEL = os.environ.get("STT_MODEL", "small")                    # whisper일 때: tiny / base / small / medium / large-v3-turbo
SENSEVOICE_DIR = os.environ.get("SENSEVOICE_DIR", f"{HERE}/models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2024-07-17")
TRANSLATE_URL = os.environ.get("TRANSLATE_URL", "http://127.0.0.1:8080/v1/chat/completions")  # OpenAI 호환 서버 (NPU든 CPU든 주소만 바꾸면 됨)
PORT = int(os.environ.get("PORT", 8000))
# ────────────────────────────────────────────────────────────────────────

results = []  # 웹에 보여줄 결과: [{"ko": "...", "en": "..."}]


# 1) 듣기: ffmpeg로 소리를 읽고, 말하는 구간을 하나씩 잘라서 내보낸다
def listen(source):
    opt = ["-rtsp_transport", "tcp"] if source.startswith("rtsp") else ["-re"]  # -re: 파일을 실시간 속도로 재생
    ffmpeg = subprocess.Popen(["ffmpeg", "-v", "error", *opt, "-i", source,
                               "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], stdout=subprocess.PIPE)
    vad = webrtcvad.Vad(2)                      # 말하는 소리인지 판별
    speech, silence = [], 0
    while len(frame := ffmpeg.stdout.read(640)) == 640:        # 20ms 조각 (16kHz, 16bit)
        if vad.is_speech(frame, 16000): speech.append(frame); silence = 0
        elif speech:                    speech.append(frame); silence += 1
        end = silence >= 40 or len(speech) >= 300              # 0.8초 조용하거나, 6초가 넘으면 거기서 자름
        if speech and end:
            if len(speech) - silence > 10:                     # 0.2초 미만의 짧은 잡음은 버림
                yield np.frombuffer(b"".join(speech), np.int16).astype(np.float32) / 32768
            speech, silence = [], 0


# 2) STT: 소리 → 한국어 텍스트   (엔진/모델은 위 설정만 수정)
if STT_ENGINE == "sensevoice":
    import sherpa_onnx
    recognizer = sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=f"{SENSEVOICE_DIR}/model.int8.onnx", tokens=f"{SENSEVOICE_DIR}/tokens.txt", num_threads=4, language="ko", use_itn=True)

    def stt(audio):
        stream = recognizer.create_stream()
        stream.accept_waveform(16000, audio)
        recognizer.decode_stream(stream)
        return stream.result.text.strip()
else:
    from faster_whisper import WhisperModel
    whisper = WhisperModel(STT_MODEL, device="cpu", compute_type="int8", cpu_threads=4)

    def stt(audio):
        segments, _ = whisper.transcribe(audio, language="ko", beam_size=1, condition_on_previous_text=False)
        return "".join(s.text for s in segments).strip()


# 3) 번역: 한국어 → 영어   (모델을 바꾸려면 TRANSLATE_URL만 수정)
def translate(ko):
    prompt = ("Translate the following Korean text to English. "
              f"Output only the English translation, nothing else.\n\nKorean: {ko}\nEnglish:")
    body = json.dumps({"model": "x", "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(TRANSLATE_URL, body, {"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))["choices"][0]["message"]["content"].strip()


# 4) 전체 흐름: 듣기 → STT → 번역 (구간을 하나씩 순서대로)
def pipeline():
    for audio in listen(SOURCE):
        t0 = time.time(); ko = stt(audio); t1 = time.time()
        if not ko: continue
        line = {"ko": ko, "en": "..."}
        results.append(line)                    # 한국어를 먼저 보여주고
        try: line["en"] = translate(ko)         # 번역이 끝나면 영어를 채움
        except Exception as e: line["en"] = f"[번역 실패: {e}]"
        print(f"소리 {len(audio)/16000:.1f}s | STT {t1-t0:.1f}s | 번역 {time.time()-t1:.1f}s | {ko} -> {line['en']}", flush=True)
    print("입력이 끝났습니다 (웹페이지는 계속 열려 있음)", flush=True)


# 5) 웹: 1초마다 /lines 를 불러와서 화면에 그린다
PAGE = """<meta charset=utf-8><body style="font:22px sans-serif;background:#111;color:#eee;white-space:pre-wrap">
<div id=o></div><script>
setInterval(async () => {
  const lines = await (await fetch('/lines')).json();
  o.replaceChildren(...lines.map(l => Object.assign(document.createElement('p'), {textContent: l.ko + '\\n→ ' + l.en})));
}, 1000);</script>"""

class Web(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/lines": body, kind = json.dumps(results[::-1]).encode(), "application/json"   # 최신 순
        else:                     body, kind = PAGE.encode(), "text/html; charset=utf-8"
        self.send_response(200); self.send_header("Content-Type", kind); self.end_headers(); self.wfile.write(body)
    def log_message(self, *args): pass

threading.Thread(target=pipeline, daemon=True).start()
print(f"http://0.0.0.0:{PORT}  (입력: {SOURCE}, STT: {STT_ENGINE})", flush=True)
ThreadingHTTPServer(("0.0.0.0", PORT), Web).serve_forever()
