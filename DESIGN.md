# voice-claude 设计文档

## 概述

voice-claude 是一个运行在 macOS 上的 Python 脚本，允许用户通过语音向 Claude CLI 输入内容。用户按住热键录音，松开后自动识别并将文字注入到 Claude CLI 终端窗口。

---

## 整体架构

```
┌─────────────────────────────────────────────────────┐
│                    voice-claude                      │
│                                                     │
│  ┌──────────┐    ┌──────────┐    ┌───────────────┐  │
│  │ 键盘监听  │───▶│  录音模块 │───▶│  STT 识别模块  │  │
│  │ pynput   │    │sounddevice│   │faster-whisper │  │
│  └──────────┘    └──────────┘    └───────┬───────┘  │
│                                          │           │
│                                          ▼           │
│                                  ┌───────────────┐  │
│                                  │  文字注入模块   │  │
│                                  │  AppleScript  │  │
│                                  └───────┬───────┘  │
└──────────────────────────────────────────┼──────────┘
                                           │
                                           ▼
                                  ┌───────────────┐
                                  │  Claude CLI   │
                                  │   终端窗口     │
                                  └───────────────┘
```

---

## 数据流

```
用户按住 Command+Shift
        │
        ▼
  开始录音（sounddevice InputStream 回调持续写入 audio_frames[]）
        │
用户松开 Command+Shift
        │
        ▼
  停止录音，合并 audio_frames → numpy array
        │
        ▼
  写入临时 .wav 文件（16kHz, mono）
        │
        ▼
  faster-whisper 转录（VAD 过滤静音，beam_size=5）
        │
        ▼
  拼接所有 segment.text → 完整字符串
        │
        ▼
  AppleScript keystroke 注入文字到最前台窗口
        │
        ▼
  AppleScript key code 36（模拟回车）发送给 Claude CLI
```

---

## 模块说明

### 键盘监听（pynput）

- 使用 `keyboard.Listener` 监听全局按键事件
- `on_press`：将按下的键加入 `pressed_keys` 集合，判断热键组合是否满足
- `on_release`：从集合中移除松开的键，判断是否应停止录音
- 热键默认为 `{Key.cmd, Key.shift}`，支持在配置区修改

### 录音模块（sounddevice）

- 使用 `sd.InputStream` 持续监听麦克风
- 采样率 16000 Hz，单声道，float32 格式（Whisper 要求）
- `audio_callback` 回调函数：仅在 `recording=True` 时将音频帧追加到 `audio_frames[]`
- 音频流全程保持打开，通过标志位控制是否保存帧，避免反复开关流带来的延迟

### STT 识别模块（faster-whisper）

- 使用 `WhisperModel` 在本地 CPU 运行，`compute_type="int8"` 降低内存占用
- 启用 VAD（Voice Activity Detection）过滤静音片段，减少误识别
- `beam_size=5` 平衡精度与速度
- 识别结果为多个 `segment`，拼接后去除首尾空白

### 文字注入模块（AppleScript）

- 通过 `subprocess.run(["osascript", ...])` 调用系统 AppleScript
- 使用 `System Events` 的 `keystroke` 模拟键盘输入
- 注入前对 `\` 和 `"` 进行转义，防止 AppleScript 解析错误
- `key code 36` 对应回车键，触发 Claude CLI 发送消息

### 线程设计

- 主线程：运行键盘监听器（`listener.join()` 阻塞）
- sounddevice 回调：在独立线程中由 PortAudio 调用
- `stop_and_transcribe`：在新 daemon 线程中执行，避免 STT 耗时阻塞键盘监听

---

## 配置项

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `SAMPLE_RATE` | `16000` | 麦克风采样率，Whisper 要求 16kHz |
| `WHISPER_MODEL` | `"small"` | 模型大小：`tiny` / `base` / `small` / `medium` |
| `LANGUAGE` | `"zh"` | 识别语言，`None` 为自动检测 |
| `HOTKEY` | `{Key.cmd, Key.shift}` | 触发热键组合 |

---

## 依赖

| 库 | 版本要求 | 用途 |
|----|---------|------|
| faster-whisper | ≥1.0 | 本地语音识别 |
| sounddevice | ≥0.4 | 麦克风录音 |
| soundfile | ≥0.12 | 写入 wav 文件 |
| pynput | ≥1.7 | 全局键盘监听 |
| numpy | ≥1.20 | 音频数据处理 |

系统依赖：
- macOS（AppleScript 注入依赖系统原生能力）
- Python 3.9+

---

## 已知限制

1. **仅支持 macOS**：文字注入通过 AppleScript 实现，不跨平台
2. **需要辅助功能权限**：`System Events keystroke` 需要终端被授权为辅助功能设备
3. **首次需联网下载模型**：使用 `hf-mirror.com` 镜像，约 480MB（small 模型）
4. **STT 有延迟**：CPU 推理，5 秒音频约需 2-3 秒识别时间
5. **注入目标为最前台窗口**：脚本运行时需确保 Claude CLI 窗口处于前台焦点
