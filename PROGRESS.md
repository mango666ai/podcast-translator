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
  → whisperX 转录（large-v3，CPU int8）        ✅
  → pyannote 说话人分离（diarization）          ← 待接入（M2）
  → Claude Code headless 翻译（意译）           ✅
  → MiniMax TTS 正文合成（逐段）               ✅ → output_zh_minimax.mp3
  → Claude 生成开场简介 + MiniMax TTS          ✅ → intro.mp3
  → ffmpeg 拼接 intro + 正文                   ✅ → final.mp3
  → generate_srt.py 生成字幕                   ✅ → .srt
  → add_chapters.py 写入 ID3 章节              ✅
  ── 后期 ──
  → F5-TTS 跨语言声音克隆                      ← M3
```

---

## 当前进度（截至 2026-06-08）

### ✅ 已完成

| 步骤 | 说明 |
|------|------|
| 环境搭建 | VideoLingo/.venv，Python 3.11.15，所有依赖已装（含 mutagen） |
| whisperX 转录 | large-v3，Mac CPU / int8，已验证：106s 转录 ~90s 音频，准确率高 |
| pyannote.audio 安装 | 4.0.4 ✅，torchcodec warning 无害，diarization 暂跳过 |
| Claude headless 翻译 | 6 段 13 秒，意译质量好，JSON 解析稳定 |
| `test_translate.py` | 翻译单元验证，快速跑通（无需音频，~15s） |
| `test_pipeline.py` | 完整链路：下载 → 转录 → 翻译 → TTS → MP3，支持断点续跑 |
| `tts_compose.py` (M1) | edge-tts 逐段合成 + ffmpeg 拼接 → `output_zh.mp3` |
| `tts_minimax.py` (M4前置) | MiniMax TTS 合成，已跑通，`output_zh_minimax.mp3` |
| `generate_srt.py` (M5a) | 生成中文 + 双语 SRT 字幕（output_zh.srt / output_bilingual.srt） |
| `intro_compose.py` (M4) | Claude 生成简介文本 → MiniMax/edge-tts 合成 → 拼接到 MP3 开头 → final.mp3 |
| `add_chapters.py` (M5c) | 写入 ID3 CHAP 章节标记（mutagen），Overcast/Pocket Casts 可跳转 |

### 🔄 下一步

- **端到端验证 M4+M5**：跑 `intro_compose.py` + `generate_srt.py` + `add_chapters.py`，确认效果
- **YouTube 下载**：bot 检测问题未解决，备选 `cookies.txt` 文件方式或 RSS 直链
- **M2**：接入 diarization，多说话人不同音色（需 HuggingFace token）

### ⏳ 里程碑

| 里程碑 | 状态 | 内容 |
|--------|------|------|
| M1 | ✅ | edge-tts + ffmpeg → output_zh.mp3 |
| M4 | ✅ 代码完成 | Claude 简介 + MiniMax TTS → intro.mp3 → final.mp3（待验证） |
| M5a | ✅ 代码完成 | SRT 字幕（中文 + 双语，待验证） |
| M5c | ✅ 代码完成 | ID3 章节标记（mutagen，待验证） |
| M2 | ⏳ | 多 speaker 分音色（接入 diarization） |
| M3 | ⏳ | F5-TTS 跨语言声音克隆 |
| M5b | ✅ | 双语 .md 已有 |

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
├── PROGRESS.md          # 本文件
├── SETUP.md             # 新机器一键环境搭建
├── .env                 # API keys（不提交 git）
├── cookies.txt          # YouTube cookies（不提交 git）
├── test_translate.py    # 翻译单元验证（最快，无需音频）
├── test_pipeline.py     # 主链路：下载 → 转录 → 翻译 → TTS → MP3
├── tts_compose.py       # M1: edge-tts 合成 → output_zh.mp3
├── tts_minimax.py       # M4前置: MiniMax TTS → output_zh_minimax.mp3
├── intro_compose.py     # M4: Claude 简介 + TTS → intro.mp3 + final.mp3
├── generate_srt.py      # M5a: 生成 SRT 字幕（中文 + 双语）
├── add_chapters.py      # M5c: 写入 ID3 章节标记
└── work/                # 中间产物（不提交 git）
    └── <job_id>/
        ├── audio.mp3
        ├── transcript.json
        ├── translation_chunk_NNN.json   ← 翻译断点续跑缓存
        ├── bilingual.md
        ├── bilingual.json
        ├── tts_segments/                ← TTS 分段缓存（断点续跑）
        │   ├── seg_0000.mp3
        │   └── ...
            ├── tts_minimax_segments/        ← MiniMax 分段缓存
        │   ├── seg_0000.mp3
        │   └── ...
        ├── output_zh.mp3                ← edge-tts 版
        ├── output_zh_minimax.mp3        ← MiniMax 版（更自然）
        ├── intro_text.txt               ← Claude 生成的简介文本
        ├── intro.mp3                    ← 开场简介音频
        ├── final.mp3                    ← 完整播客（intro + 正文 + 章节）✓
        ├── output_zh.srt                ← 中文字幕
        └── output_bilingual.srt         ← 双语字幕
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
python tts_compose.py work/<job_id>                  # edge-tts
python tts_minimax.py work/<job_id>                  # MiniMax（需 .env 中有 key）

# ⑦ M4：生成开场简介并拼接
python intro_compose.py work/<job_id>                # → final.mp3

# ⑧ M5a：生成 SRT 字幕
python generate_srt.py work/<job_id>                 # → output_zh.srt / output_bilingual.srt

# ⑨ M5c：写入 ID3 章节
python add_chapters.py work/<job_id>                 # 默认 5 分钟一章
python add_chapters.py work/<job_id> --interval 180  # 3 分钟一章

# ⑩ 播放结果
open work/<job_id>/final.mp3
```
