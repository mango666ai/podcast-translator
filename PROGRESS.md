# 播客翻译项目 — 进度记录

## 项目目标
把英文播客（YouTube / RSS / 本地音频）一键转成中文 MP3，供通勤收听。
- 开头女声旁白简介（~1 分钟）
- 正文中文配音（MiniMax TTS / edge-tts）
- 双语对照 .md + .srt 字幕
- ID3 章节标记
- 自动上传飞书云盘

## 仓库 & 本地路径

| 项目 | GitHub | 本地路径 |
|------|--------|---------|
| 本项目 | `mango666ai/podcast-translator` | `~/Documents/CCtest/podcast-translator` |
| VideoLingo（依赖） | `Huanshere/VideoLingo` | `~/Documents/CCtest/VideoLingo` |
| Python venv | — | `~/Documents/CCtest/VideoLingo/.venv`（Python 3.11.15） |

## 飞书配置

| 项目 | 值 |
|------|---|
| 飞书应用 | `cli_a92330864c785bde` |
| 云盘文件夹 | 播客翻译 |
| folder_token | `ZEtzfLmtYlsv4Ddoi3WcH0AYnnp` |
| 文件夹链接 | https://m0c4oiqy715.feishu.cn/drive/folder/ZEtzfLmtYlsv4Ddoi3WcH0AYnnp |

## 技术链路（当前完整版）

```
音频输入（YouTube / RSS / 本地）
  → yt-dlp 下载                                ✅
  → whisperX 转录（large-v3，CPU int8）         ✅
  → pyannote 说话人分离（diarization）          ← 待接入（M2）
  → Claude Code headless 翻译（意译）           ✅
  → MiniMax TTS 正文合成（逐段）               ✅ → output_zh_minimax.mp3
  → Claude 生成开场简介 + MiniMax TTS          ✅ → intro.mp3
  → ffmpeg 拼接 intro + 正文                   ✅ → final.mp3
  → generate_srt.py 生成字幕                   ✅ → .srt
  → add_chapters.py 写入 ID3 章节              ✅
  → upload_feishu.py 上传飞书云盘              ✅
  ── 后期 ──
  → F5-TTS 跨语言声音克隆                      ← M3
```

---

## 当前进度（截至 2026-06-08）

### ✅ 已完成

| 步骤 | 说明 |
|------|------|
| 环境搭建 | VideoLingo/.venv，Python 3.11.15，含 mutagen / edge-tts / whisperX 等全部依赖 |
| whisperX 转录 | large-v3，Mac CPU / int8，已验证 |
| Claude headless 翻译 | 意译质量好，JSON 解析稳定，支持断点续跑 |
| `test_pipeline.py` | 完整链路：下载 → 转录 → 翻译，支持断点续跑、cookies.txt |
| `tts_compose.py` (M1) | edge-tts 逐段合成 + ffmpeg 拼接 → `output_zh.mp3` |
| `tts_minimax.py` | MiniMax TTS 合成，已跑通 → `output_zh_minimax.mp3`，含 `--preview` 试听模式 |
| `intro_compose.py` (M4) | Claude 生成简介 → MiniMax/edge-tts → intro.mp3 → 拼接为 final.mp3 |
| `generate_srt.py` (M5a) | 从 bilingual.json 生成中文 + 双语 SRT 字幕 |
| `add_chapters.py` (M5c) | 写入 ID3 CHAP 章节标记（mutagen），Overcast / Pocket Casts 可跳转 |
| `upload_feishu.py` | 自动上传 MP3 + SRT 到飞书云盘「播客翻译」文件夹，记录上传结果 |

### 🔄 下一步

- **端到端跑一遍真实播客**：验证 M4（简介）+ M5（字幕+章节）+ 飞书上传完整流程
- **YouTube 下载**：bot 检测问题，备选 `cookies.txt` 文件方式或 RSS 直链
- **M2**：接入 diarization 多说话人分音色（需 HuggingFace token）

### ⏳ 里程碑

| 里程碑 | 状态 | 内容 |
|--------|------|------|
| M0 | ✅ | 下载 + 转录 + 翻译 pipeline |
| M1 | ✅ | edge-tts + ffmpeg → output_zh.mp3 |
| M4 | ✅ 代码完成 | Claude 简介 + MiniMax TTS → intro.mp3 → final.mp3 |
| M5a | ✅ 代码完成 | SRT 字幕（中文 + 双语） |
| M5b | ✅ | 双语 .md 已有 |
| M5c | ✅ 代码完成 | ID3 章节标记（mutagen） |
| 飞书上传 | ✅ | 自动上传到飞书云盘「播客翻译」 |
| M2 | ⏳ | 多 speaker 分音色（接入 diarization） |
| M3 | ⏳ | F5-TTS 跨语言声音克隆 |

---

## 已知问题 & 解决方案

| 问题 | 解决方案 |
|------|---------|
| YouTube bot 检测 | 把 cookies.txt 放项目根目录自动识别；或用 RSS 直链 |
| torchcodec warning（pyannote import 时） | 无害，自动 fallback soundfile，忽略即可 |
| claude 模型名 | 始终用 `--model claude-sonnet-4-5` |
| 磁盘空间 | venv ~5GB，whisper large-v3 首次下载 ~3GB（`~/.cache/huggingface/`） |
| MiniMax 声音 ID | 国际版用英文 ID：`Wise_Woman`、`Calm_Woman` 等（非 `Podcast_female`） |

---

## 关键文件

```
podcast-translator/
├── PROGRESS.md          # 本文件
├── SETUP.md             # 新机器一键环境搭建
├── .env                 # API keys（不提交 git）MINIMAX_API_KEY=xxx
├── cookies.txt          # YouTube cookies（不提交 git）
├── test_translate.py    # 翻译单元验证（最快，无需音频）
├── test_pipeline.py     # 主链路：下载 → 转录 → 翻译
├── tts_compose.py       # M1: edge-tts 合成 → output_zh.mp3
├── tts_minimax.py       # MiniMax TTS → output_zh_minimax.mp3 / --preview 试听
├── intro_compose.py     # M4: Claude 简介 + TTS → intro.mp3 → final.mp3
├── generate_srt.py      # M5a: 生成 SRT 字幕（中文 + 双语）
├── add_chapters.py      # M5c: 写入 ID3 章节标记
├── upload_feishu.py     # 上传产物到飞书云盘「播客翻译」文件夹
└── work/                # 中间产物（不提交 git）
    └── <job_id>/
        ├── audio.mp3
        ├── transcript.json
        ├── translation_chunk_NNN.json   ← 翻译断点续跑缓存
        ├── bilingual.md / bilingual.json
        ├── tts_segments/                ← edge-tts 分段缓存
        ├── tts_minimax_segments/        ← MiniMax 分段缓存
        ├── output_zh.mp3                ← edge-tts 版
        ├── output_zh_minimax.mp3        ← MiniMax 版（更自然）
        ├── intro_text.txt               ← Claude 生成的简介文本
        ├── intro.mp3                    ← 开场简介音频
        ├── final.mp3                    ← 完整播客（intro + 正文 + 章节）✓
        ├── output_zh.srt                ← 中文字幕
        ├── output_bilingual.srt         ← 双语字幕
        └── feishu_upload.json           ← 上传记录（含飞书文件链接）
```

---

## 换机器 / 下次工作从这里开始

```bash
# ① 克隆代码（新机器）
cd ~/Documents/CCtest
git clone https://github.com/mango666ai/podcast-translator.git podcast-translator
git clone --depth 1 https://github.com/Huanshere/VideoLingo.git VideoLingo

# ② 搭环境 — 详见 SETUP.md（约 10 分钟）

# ③ 激活环境（每次开工前）
cd ~/Documents/CCtest/podcast-translator
source ../VideoLingo/.venv/bin/activate

# ④ 完整流程（一集播客）
python test_pipeline.py /path/to/audio.mp3 --no-tts   # 转录 + 翻译
python tts_minimax.py work/<job_id>                    # MiniMax TTS 合成
python intro_compose.py work/<job_id>                  # 开场简介 → final.mp3
python generate_srt.py work/<job_id>                   # 生成字幕
python add_chapters.py work/<job_id>                   # 写入章节标记
python upload_feishu.py work/<job_id> --title "标题"   # 上传飞书云盘

# ⑤ 播放验收
open work/<job_id>/final.mp3
```
