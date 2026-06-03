# 播客翻译项目 — 进度记录

## 项目目标
把英文播客（YouTube / RSS / 本地音频）一键转成中文 MP3，供通勤收听。
- 开头女声旁白简介（~1 分钟）
- 正文中文配音（多说话人克隆音色，F5-TTS）
- 双语对照 .md + .srt 字幕
- ID3 章节标记

## 仓库 & 本地路径

| 项目 | GitHub | 本地路径 |
|------|--------|---------|
| 本项目 | `mango666ai/podcast-translator` | `~/Documents/CCtest/podcast-translator` |
| VideoLingo（依赖） | `Huanshere/VideoLingo` | `~/Documents/CCtest/VideoLingo` |
| Python venv | — | `~/Documents/CCtest/VideoLingo/.venv`（Python 3.11.15） |

## 技术链路

```
音频输入（YouTube / RSS / 本地）
  → yt-dlp 下载
  → whisperX 转录（large-v3，CPU int8）
  → pyannote 说话人分离（diarization）       ← 待接入
  → Claude Code headless 翻译（意译）
  → edge-tts 中文语音合成（逐段）
  → ffmpeg 拼接 → output_zh.mp3
  ── 后期 ──
  → F5-TTS 跨语言声音克隆                   ← M3
  → MiniMax TTS 女声开场简介                ← M4
  → ID3 章节 + 双语 .md + .srt              ← M5
```

---

## 当前进度（截至 2026-06-03）

### ✅ 已完成

| 步骤 | 说明 |
|------|------|
| 环境搭建 | VideoLingo/.venv，Python 3.11.15，所有依赖已装（见下方清单） |
| whisperX 转录 | large-v3，Mac CPU / int8，已验证：106s 转录 ~90s 音频，准确率高 |
| pyannote.audio 安装 | 4.0.4 ✅，torchcodec warning 无害（fallback soundfile），diarization 暂跳过 |
| Claude headless 翻译 | 6 段 13 秒，意译质量好，JSON 解析稳定 |
| `test_translate.py` | 翻译单元验证，快速跑通（无需音频，~15s） |
| `test_pipeline.py` | 完整链路：下载 → 转录 → 翻译 → TTS → MP3，支持断点续跑 |
| `tts_compose.py` (M1) | edge-tts 逐段合成 + ffmpeg 拼接 → `output_zh.mp3`，声音可选，断点续跑 |

### 🔄 下一步（待验证）

- **端到端验证**：拿一段本地 mp3 跑完整 4 步 pipeline，实际播放 `output_zh.mp3` 听效果
- **YouTube 下载**：bot 检测问题未解决（`--cookies-from-browser safari` macOS Keychain 权限受限），备选 RSS 直链

### ⏳ 里程碑

| 里程碑 | 状态 | 内容 |
|--------|------|------|
| M1 | 代码完成，待验证 | edge-tts + ffmpeg → output_zh.mp3 |
| M2 | ⏳ | 多 speaker 分音色（接入 diarization） |
| M3 | ⏳ | F5-TTS 跨语言声音克隆 |
| M4 | ⏳ | MiniMax TTS 女声开场简介 |
| M5 | ⏳ | ID3 章节 + 双语 .md + .srt |

---

## 已知问题 & 解决方案

| 问题 | 解决方案 |
|------|---------|
| YouTube bot 检测 | `--cookies-from-browser safari`，需先在 Safari 登录 YouTube；macOS 有 Keychain 权限限制，失败时改用 RSS 直链 |
| torchcodec warning（pyannote import 时） | 无害，自动 fallback 到 soundfile，忽略即可 |
| claude 模型名 | 始终用 `--model claude-sonnet-4-5`，不依赖默认值 |
| 磁盘空间 | venv ~5GB，whisper large-v3 模型首次下载 ~3GB（缓存在 `~/.cache/huggingface/`） |

---

## 关键文件

```
podcast-translator/
├── PROGRESS.md         # 本文件
├── SETUP.md            # 新机器一键环境搭建
├── test_translate.py   # 翻译单元验证（最快，无需音频）
├── test_pipeline.py    # 主链路：下载 → 转录 → 翻译 → TTS → MP3
├── tts_compose.py      # M1 独立 TTS 脚本（可单独运行）
└── work/               # 中间产物（不提交 git）
    └── <job_id>/
        ├── audio.mp3
        ├── transcript.json
        ├── translation_chunk_NNN.json   ← 翻译断点续跑缓存
        ├── bilingual.md
        ├── bilingual.json
        ├── tts_segments/                ← TTS 分段缓存（断点续跑）
        │   ├── seg_0000.mp3
        │   └── ...
        └── output_zh.mp3                ← 最终中文 MP3 ✓
```

---

## 换机器 / 下次工作从这里开始

```bash
# ① 克隆代码（新机器）
cd ~/Documents/CCtest
git clone https://github.com/mango666ai/podcast-translator.git podcast-translator
git clone --depth 1 https://github.com/Huanshere/VideoLingo.git VideoLingo

# ② 搭环境（新机器）— 详见 SETUP.md
# 按 SETUP.md 步骤执行即可，约 10 分钟

# ③ 激活环境（每次开工前）
cd ~/Documents/CCtest/podcast-translator
source ../VideoLingo/.venv/bin/activate

# ④ 验证翻译（最轻量，约 15 秒）
python test_translate.py

# ⑤ 跑完整 pipeline（本地 mp3）
python test_pipeline.py /path/to/audio.mp3 --duration 90   # 先测 90 秒
python test_pipeline.py /path/to/audio.mp3 --duration 0    # 全量

# ⑥ 只补 TTS 步骤（pipeline 已跑过）
python tts_compose.py work/<job_id>

# ⑦ 播放结果
open work/<job_id>/output_zh.mp3

# 声音选项
# zh-CN-XiaoxiaoNeural  女声，自然亲切（默认）
# zh-CN-YunjianNeural   男声，沉稳
# python test_pipeline.py audio.mp3 --voice zh-CN-YunjianNeural
```
