# 🎙 podcast-translator

把英文播客一键转成中文 MP3，供通勤收听。

- 🗣 whisperX / YouTube 英文字幕转写 + DeepSeek 意译
- 🔊 MiniMax 或 CosyVoice 原声克隆中文配音
- 📖 六段式节目笔记进入 RSS 简介
- 📄 双语 SRT 字幕
- 🎧 staging RSS 试听确认后再转正式

---

## 当前生产流程

```bash
cd ~/AIcoding/project5_podcast/podcast_addon
source ../VideoLingo/.venv/bin/activate

# 下载/转写 → DeepSeek 翻译 → 说话人规则 → 原声克隆 TTS
# 完整命令与验收项见《播客工作循环.md》
```

实际生产链路由 `youtube_transcribe.py`、`youtube_dub.py`、`build_speaker_rules.py`、`youtube_multivoice_dub.py`、`stage_episode.py` 和 `publish_from_staging.py` 组成。Codex 执行门禁见 [CODEX_RUNBOOK.md](CODEX_RUNBOOK.md)；翻译后用 `audit_translation.py`，发布前后用 `podcast_doctor.py`。

⚠️ `run_jobs.py` 仍连接旧的 `test_pipeline.py` 链路，当前只能视作遗留工具，不能代表正式生产流程已经全自动化。

**当前工作规范：** 详见 `播客工作循环.md`。完整中文音频才算完成；英文原始音频、英文转写、小样都只是中间状态。

---

## 完整手动流程

```bash
# 例：把已试听确认的一集从 staging 转正式
python publish_from_staging.py <video_id> \
  --pub-date "Thu, 08 Oct 2026 10:00:00 +0000" \
  --multivoice
```

新集从下载到 staging 的详细步骤、参数和验收规则，以 [播客工作循环.md](播客工作循环.md) 为唯一真相源。

---

## 换机器重新搭建

详见 [SETUP.md](SETUP.md)，约 10 分钟。

```bash
cd ~/Documents/CCtest
git clone https://github.com/mango666ai/podcast-translator.git podcast-translator
git clone --depth 1 https://github.com/Huanshere/VideoLingo.git VideoLingo
# 然后按 SETUP.md 步骤执行
```

---

## 飞书配置

| 项目 | 地址 |
|------|------|
| 任务队列（多维表格） | （见私有笔记仓库 aicoding-notes/project5_podcast/PROJECT_MAP.md） |
| 产物云盘文件夹 | （见私有笔记仓库 aicoding-notes/project5_podcast/PROJECT_MAP.md） |

---

## 文件说明

| 文件 | 作用 |
|------|------|
| `run_jobs.py` | 旧任务队列编排器，尚未接入当前生产链路 |
| `test_pipeline.py` | 旧链路：下载 → 转录 → 翻译 |
| `tts_minimax.py` / `tts_cosyvoice.py` | 两个正式 TTS 供应商适配层 |
| `intro_compose.py` | OpenAI GPT 生成简介 + TTS → 拼接 final.mp3 |
| `generate_srt.py` | 生成中文 / 双语 SRT 字幕 |
| `add_chapters.py` | 写入 ID3 章节标记 |
| `upload_feishu.py` | 上传产物到飞书云盘 |
| `tts_compose.py` | edge-tts 备用合成 |
| `youtube_transcribe.py` | 批量 YouTube 下载 + 英文转写，用于 8 个视频的第一阶段 |
| `youtube_dub.py` | 基于转写调用 OpenAI GPT 生成中文字幕 / 中文配音小样 / 完整中文音频 |
| `stage_episode.py` / `publish_from_staging.py` | staging 入库与转正式发布 |
| `audit_translation.py` | 双语分段静态质量审计（不替代人工语义复核） |
| `podcast_doctor.py` | RSS、状态表和公开产物一致性检查 |
| `podcast_status.csv` | 逐集机器状态表 |
| `.env` | API Keys（不提交）：DeepSeek、MiniMax、DashScope 等 |
| `cookies.txt` | YouTube cookies（不提交）|
