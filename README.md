# voice-claude 使用文档

语音输入工具，按住快捷键说话，松开后自动将识别的文字发送到 Claude CLI。

---

## 环境要求

- macOS
- Python 3.9+

---

## 安装

**1. 安装依赖**

```bash
cd ~/code/python/Projects/voice-claude
python3 -m pip install -r requirements.txt
```

**2. 授权辅助功能权限**

系统设置 → 隐私与安全性 → 辅助功能 → 点击 `+` → 添加你的终端（Terminal 或 iTerm2）

> 不授权则文字无法注入到终端窗口

---

## 运行

```bash
python3 ~/code/python/Projects/voice-claude/main.py
```

首次运行会自动下载 Whisper 模型（约 480MB），下载完成后显示：

```
[voice-claude] 就绪。按住 Command+Shift 录音，松开发送。Ctrl+C 退出
```

---

## 使用方式

**准备**

1. 打开两个终端窗口
2. 窗口 A 运行 `python3 ~/code/python/Projects/voice-claude/main.py`
3. 窗口 B 运行 `claude` 启动 Claude CLI

**录音输入**

1. 点击窗口 B（Claude CLI），使其获得焦点
2. 按住 `Command + Shift` 开始说话
3. 说完后松开按键
4. 等待识别完成，文字自动输入并发送

**终端输出示例**

```
[voice-claude] 🎙  录音中... 识别中...
[voice-claude] 识别结果：帮我写一个快速排序算法
```

**退出**

在窗口 A 按 `Ctrl+C`

---

## 配置

打开 `main.py`，修改文件顶部的配置区：

```python
WHISPER_MODEL = "small"   # 模型大小，影响速度和精度
LANGUAGE = "zh"           # 识别语言，None 为自动检测
HOTKEY = {Key.cmd, Key.shift}  # 触发热键
```

**模型选择参考**

| 模型 | 文件大小 | 识别速度 | 中文精度 |
|------|---------|---------|---------|
| tiny | 75MB | 最快 | 一般 |
| base | 145MB | 快 | 较好 |
| small | 480MB | 中等 | 好（推荐） |
| medium | 1.5GB | 慢 | 更好 |

---

## 常见问题

**Q：首次运行下载模型超时**

网络不稳定导致，重新运行脚本会继续下载。也可以先单独下载模型：

```bash
python3 -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"
```

如果持续超时，改用 tiny 模型（75MB）：

在 `main.py` 中将 `WHISPER_MODEL = "small"` 改为 `WHISPER_MODEL = "tiny"`

---

**Q：文字输入到了错误的窗口**

松开热键前需确保 Claude CLI 窗口处于前台焦点（被点击激活状态）。

---

**Q：提示「输入失败」**

未授权辅助功能权限。按以下步骤操作：

系统设置 → 隐私与安全性 → 辅助功能 → 添加终端应用

---

**Q：识别内容不准确**

- 说话时靠近麦克风，减少背景噪音
- 改用更大的模型（`medium`）提升精度
- 将 `LANGUAGE = "zh"` 改为 `LANGUAGE = None` 让模型自动判断语言

---

## 项目结构

```
voice-claude/
├── main.py          # 主程序
├── requirements.txt # 依赖列表
├── README.md        # 使用文档
└── DESIGN.md        # 设计文档
```
