#!/usr/bin/env python3
"""
voice-claude: 语音输入到 Claude CLI 工具
按住 Command+Shift 录音，松开后自动识别并输入到终端
"""

import os
import sys
import time
import tempfile
import threading
import subprocess
import numpy as np
import sounddevice as sd
import soundfile as sf
from pynput import keyboard
from faster_whisper import WhisperModel

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")

# ── 配置 ──────────────────────────────────────────────────────────────────────
SAMPLE_RATE = 16000
WHISPER_MODEL = "small"
LANGUAGE = "zh"
HOTKEY = {keyboard.Key.cmd, keyboard.Key.shift}
# ─────────────────────────────────────────────────────────────────────────────

recording = False
audio_frames = []
pressed_keys = set()
model = None

own_window   = {"app": None, "title": None}  # 脚本自身的终端窗口
target_window = {"app": None, "title": None}  # 用户最后点击的其他窗口
_lock = threading.Lock()


def get_frontmost_window():
    """获取当前最前台的应用名和窗口标题"""
    script = '''
    tell application "System Events"
        set frontApp to first application process whose frontmost is true
        set appName to name of frontApp
        try
            set winTitle to name of front window of frontApp
        on error
            set winTitle to ""
        end try
        return appName & "||" & winTitle
    end tell
    '''
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    parts = r.stdout.strip().split("||", 1)
    return (parts[0] if parts else ""), (parts[1] if len(parts) > 1 else "")


def window_tracker():
    """后台线程：持续记录用户最后点击的非脚本窗口作为注入目标"""
    global target_window
    while True:
        try:
            app, title = get_frontmost_window()
            is_own = (app == own_window["app"] and title == own_window["title"])
            if app and not is_own:
                with _lock:
                    target_window = {"app": app, "title": title}
        except Exception:
            pass
        time.sleep(0.3)


def load_model():
    global model
    print(f"[voice-claude] 正在加载 Whisper {WHISPER_MODEL} 模型...")
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
    print("[voice-claude] 模型加载完成")


def start_recording():
    global recording, audio_frames
    audio_frames = []
    recording = True
    print("[voice-claude] 🎙  录音中...", end="", flush=True)


def stop_and_transcribe():
    global recording
    recording = False
    print(" 识别中...", end="", flush=True)

    if not audio_frames:
        print(" 未检测到音频")
        return

    audio_data = np.concatenate(audio_frames, axis=0).flatten()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        tmp_path = tmp.name
        sf.write(tmp_path, audio_data, SAMPLE_RATE)

    segments, _ = model.transcribe(
        tmp_path,
        language=LANGUAGE,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    text = "".join(seg.text for seg in segments).strip()

    if not text:
        print(" 未识别到内容")
        return

    print(f"\n[voice-claude] 识别结果：{text}")
    inject_text(text)


def inject_text(text):
    """将文字通过剪贴板注入到用户最后点击的窗口"""
    with _lock:
        app   = target_window.get("app") or ""
        title = target_window.get("title") or ""

    if not app:
        print("[voice-claude] 未检测到目标窗口，请先点击 Claude CLI 的终端窗口")
        return

    print(f"[voice-claude] → 注入到: [{app}] {title}")

    safe_title = title.replace("\\", "\\\\").replace('"', '\\"')

    # 1. 写入剪贴板（支持中文 Unicode，keystroke 不支持）
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), capture_output=True)

    # 2. 通过标题找到目标窗口并激活，然后粘贴
    script = f'''
    tell application "System Events"
        tell process "{app}"
            set frontmost to true
            repeat with w in every window
                if name of w contains "{safe_title}" then
                    perform action "AXRaise" of w
                    exit repeat
                end if
            end repeat
        end tell
        delay 0.3
        keystroke "v" using command down
        delay 0.05
        key code 36
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[voice-claude] 注入失败: {result.stderr.strip()}")


def audio_callback(indata, frames, time_info, status):
    if recording:
        audio_frames.append(indata.copy())


def on_press(key):
    pressed_keys.add(key)
    if HOTKEY.issubset(pressed_keys) and not recording:
        start_recording()


def on_release(key):
    if key in pressed_keys:
        pressed_keys.discard(key)
    if recording and not HOTKEY.issubset(pressed_keys):
        threading.Thread(target=stop_and_transcribe, daemon=True).start()


def main():
    global own_window

    # 记录脚本自身所在的终端窗口
    app, title = get_frontmost_window()
    own_window = {"app": app, "title": title}
    print(f"[voice-claude] 脚本运行于: [{app}] {title}")

    load_model()

    # 启动后台窗口追踪线程
    threading.Thread(target=window_tracker, daemon=True).start()

    print("[voice-claude] 请点击 Claude CLI 的终端窗口，脚本会自动将其设为目标")

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        callback=audio_callback,
    ):
        with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
            print("[voice-claude] 就绪。按住 Command+Shift 录音，松开发送。Ctrl+C 退出")
            try:
                listener.join()
            except KeyboardInterrupt:
                print("\n[voice-claude] 已退出")
                sys.exit(0)


if __name__ == "__main__":
    main()
