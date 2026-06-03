# 新机器环境搭建

验证可用的步骤（2026-06-03 实测于 macOS Apple Silicon）。

## 前提条件
- macOS（Apple Silicon / Intel 均可）
- 磁盘可用空间 ≥ 10GB（venv ~5GB + whisper 模型 ~3GB）
- Homebrew 已安装：https://brew.sh

---

## 步骤

### 1. 系统依赖

```bash
brew install ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.zshrc   # 或重开终端让 uv 生效
```

### 2. 克隆代码

```bash
mkdir -p ~/Documents/CCtest && cd ~/Documents/CCtest
git clone https://github.com/mango666ai/podcast-translator.git podcast-translator
git clone --depth 1 https://github.com/Huanshere/VideoLingo.git VideoLingo
```

### 3. 创建 Python 3.11 venv

```bash
cd ~/Documents/CCtest
uv venv VideoLingo/.venv --python 3.11
```

### 4. 安装依赖（顺序执行）

```bash
PYTHON=~/Documents/CCtest/VideoLingo/.venv/bin/python3.11

# PyTorch（Apple Silicon 用 CPU，无需 CUDA）
uv pip install torch==2.8.0 torchaudio==2.8.0 --python $PYTHON

# 语音转录
uv pip install whisperx --python $PYTHON

# 说话人分离（import 时有 torchcodec warning，无害）
uv pip install "pyannote.audio>=3.1" --python $PYTHON

# TTS & 音频处理
uv pip install edge-tts pydub soundfile librosa --python $PYTHON

# 工具库
uv pip install openpyxl ruamel.yaml "openai>=1.55.3" json-repair ctranslate2 --python $PYTHON
```

### 5. 安装 yt-dlp

```bash
uv tool install yt-dlp
```

### 6. 登录 Claude Code

```bash
claude   # 进入后 /login，浏览器完成认证
```

### 7. 验证安装

```bash
cd ~/Documents/CCtest/podcast-translator
source ../VideoLingo/.venv/bin/activate

# 检查所有包
python -c "
import torch, whisperx, edge_tts, pyannote.audio
import pydub, librosa, soundfile, json_repair, openai, openpyxl
print('torch', torch.__version__)
print('pyannote.audio', pyannote.audio.__version__)
print('所有核心包 ✅')
"

# 快速验证翻译（约 15 秒，无需音频）
python test_translate.py
```

首次跑 `test_pipeline.py` 时会自动下载 whisper large-v3 模型（~3GB），请耐心等待。

---

## 注意事项

| 问题 | 说明 |
|------|------|
| torchcodec warning | pyannote import 时出现，无害，自动 fallback soundfile |
| YouTube 下载 | 需先在 Safari 登录 YouTube，再用 `--cookies-from-browser safari` |
| 磁盘空间 | venv ~5GB，huggingface 模型缓存 `~/.cache/huggingface/` ~3GB |
| Claude 模型名 | 始终用 `--model claude-sonnet-4-5`，不依赖默认值 |

---

## 目录结构（搭完后）

```
~/Documents/CCtest/
├── VideoLingo/          # 开源仓库（--depth 1，仅做依赖用）
│   └── .venv/           # Python 3.11 venv，所有依赖在这里
└── podcast-translator/  # 本项目
    ├── PROGRESS.md
    ├── SETUP.md
    ├── test_translate.py
    ├── test_pipeline.py
    ├── tts_compose.py
    └── work/            # 中间产物（git ignore）
```
