# 新机器环境搭建

## 前提条件
- macOS（Apple Silicon / Intel 均可）
- 磁盘可用空间 ≥ 8GB
- Homebrew 已安装（[brew.sh](https://brew.sh)）

## 步骤

### 1. 克隆代码
```bash
cd ~/Documents   # 或你想放的目录
git clone https://github.com/caimengge/podcast-translator.git podcast_addon
git clone --depth 1 https://github.com/Huanshere/VideoLingo.git VideoLingo
```

### 2. 安装系统依赖
```bash
brew install ffmpeg
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.zshrc   # 或重开终端
```

### 3. 创建 Python 环境并安装依赖
```bash
cd VideoLingo
uv venv .venv --python 3.11
uv pip install torch==2.8.0 torchaudio==2.8.0 --python .venv/bin/python3.11
uv pip install --no-deps "demucs[dev]@git+https://github.com/adefossez/demucs"
uv pip install dora-search openunmix lameenc --python .venv/bin/python3.11
uv pip install whisperx "pyannote.audio>=3.1" --python .venv/bin/python3.11
uv pip install openpyxl ruamel.yaml "openai>=1.55.3" edge-tts pydub json-repair librosa soundfile ctranslate2 --python .venv/bin/python3.11
uv pip install -e . --python .venv/bin/python3.11
```

### 4. 安装 yt-dlp
```bash
uv tool install yt-dlp
```

### 5. 登录 Claude Code
```bash
claude   # 进入后输入 /login，完成浏览器认证
```

### 6. 验证安装
```bash
cd ../podcast_addon
export PATH="$HOME/.local/bin:$HOME/.homebrew/bin:$PATH"
export DYLD_LIBRARY_PATH="$HOME/.homebrew/lib:$DYLD_LIBRARY_PATH"

# 快速验证翻译（约 15 秒）
python test_translate.py

# 完整 pipeline（首次会下载 whisper large-v3 模型 ~3GB）
python test_pipeline.py work/test_local/audio.mp3
```

## 注意事项
- **whisper large-v3 模型**：首次转录时自动下载，约 3GB，缓存在 `~/.cache/huggingface/`
- **磁盘空间**：安装完依赖约占 5-6GB，模型再占 ~4GB
- **torchcodec 警告**：可以忽略，不影响功能
- **YouTube 下载**：需要 `--cookies-from-browser safari`，macOS 下需要先在 Safari 登录 YouTube
