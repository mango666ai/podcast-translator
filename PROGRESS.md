# 播客翻译项目 — 进度记录

## 项目目标
把英文播客（YouTube / RSS / 本地音频）一键转成中文 MP3，供通勤收听。
- 开头女声旁白简介（~1 分钟）
- 正文中文配音（多说话人克隆音色，F5-TTS）
- 双语对照 .md + .srt 字幕
- ID3 章节标记

## 技术方案
基于 **VideoLingo**（`Huanshere/VideoLingo`）改造，而非从零写。

### 完整技术链路
```
音频输入（YouTube/RSS/本地）
  → yt-dlp 下载
  → demucs 人声分离
  → whisperX 转录（large-v3）
  → pyannote 说话人分离（diarization）  ← 待做
  → Claude Code headless 翻译（意译）
  → F5-TTS 跨语言声音克隆（正文）       ← 待做
  → MiniMax TTS 女声（开场简介）         ← 待做
  → ffmpeg 拼接 + ID3 章节
  → 输出 MP3 + .md + .srt
```

---

## 当前进度（截至 2026-06-03）

### ✅ 已完成
| 步骤 | 状态 | 说明 |
|---|---|---|
| 环境搭建 | ✅ | Python 3.11 venv，见下方 setup 说明 |
| whisperX 安装 | ✅ | large-v3，Mac CPU/int8 |
| pyannote 安装 | ✅ | 已装但未配置（跳过 diarization 先跑通主流程） |
| Claude headless 翻译验证 | ✅ | 6 段 13 秒，质量好，JSON 解析稳定 |
| 本地音频转录验证 | ✅ | 106 秒转录 ~90 秒音频，3 段识别准确 |
| test_translate.py | ✅ | 独立翻译测试脚本 |
| test_pipeline.py | ✅ | 下载+转录+翻译一体脚本，断点续跑 |

### 🔄 进行中（下一步）
- **test_pipeline.py 跑通最后一步**：翻译阶段因 claude model name 问题失败，已修复（`--model claude-sonnet-4-5`），待验证
- YouTube 下载：需要处理 bot 检测（`--cookies-from-browser` 在 macOS 有权限问题，待解决）

### ⏳ 待做
| 里程碑 | 内容 |
|---|---|
| M1 | 输出 MP3（post pipeline：extract_mp3, compose） |
| M2 | 多 speaker 分音色（接入 diarization，dispatch 链路） |
| M3 | 本地 F5-TTS 跨语言克隆 |
| M4 | 简介旁白（MiniMax TTS 女声） |
| M5 | ID3 章节 + 双语 .md + .srt 输出 |

---

## 已知问题 & 解决方案

| 问题 | 解决方案 |
|---|---|
| YouTube 下载被 bot 检测 | 用 `--cookies-from-browser safari/chrome`，macOS 有 Keychain 权限限制；备选：RSS 直链下载 |
| torchcodec 警告（`libavutil.59.dylib not found`） | 无害，pyannote 自动 fallback 到 soundfile；忽略即可 |
| claude 模型名问题 | 始终用 `--model claude-sonnet-4-5`，不依赖默认配置 |
| 磁盘空间 | 项目装完约占 5-6GB，确保至少 8GB 可用再开始 |

---

## 换电脑继续工作

见 `SETUP.md`，按步骤执行即可。

---

## 关键文件说明

```
podcast_addon/
├── PROGRESS.md          # 本文件，当前进度
├── SETUP.md             # 新机器一键环境搭建
├── test_translate.py    # 翻译单元验证（不需要音频，快速跑通）
├── test_pipeline.py     # 主链路验证（下载+转录+翻译）
└── work/                # 中间产物（不提交 git）
    └── <job_id>/
        ├── audio.mp3
        ├── transcript.json
        ├── translation_chunk_NNN.json  ← 断点续跑缓存
        └── bilingual.md
```

---

## 下次工作从这里开始

```bash
# 1. 确认环境
cd ~/Documents/AI实践/podcast_addon
source ../VideoLingo/.venv/bin/activate

# 2. 验证翻译链路（最轻量的测试）
python test_translate.py

# 3. 跑完整 pipeline（本地音频）
python test_pipeline.py work/test_local/audio.mp3 --duration 0

# 4. 尝试 YouTube（需要 cookies）
python test_pipeline.py "https://youtube.com/watch?v=xxx" --duration 90
```
