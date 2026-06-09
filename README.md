# 🎙 podcast-translator

把英文播客一键转成中文 MP3，供通勤收听。

- 🗣 whisperX 转录 + Claude 意译
- 🔊 MiniMax TTS 中文配音（自然女声）
- 📖 开场简介 + ID3 章节标记
- 📄 双语 SRT 字幕
- ☁️ 自动上传飞书云盘

---

## 每次开机后运行

```bash
# 1. 进入项目目录，激活环境
cd ~/Documents/CCtest/podcast-translator
source ../VideoLingo/.venv/bin/activate

# 2. 启动任务队列（处理飞书表单提交的任务）
python run_jobs.py --loop
```

`--loop` 模式每 5 分钟自动检查飞书多维表格，有新任务就开始处理，处理完自动更新状态并上传飞书云盘。

**提交任务：** 用手机打开飞书多维表格「播客任务队列」→ 填写表单「提交播客任务」

---

## 手动处理单条任务

```bash
# 只处理一条，处理完退出
python run_jobs.py

# dry-run 模式：只打印任务，不实际处理
python run_jobs.py --dry-run
```

---

## 完整手动流程（不用飞书表单）

```bash
source ../VideoLingo/.venv/bin/activate

# 转录 + 翻译
python test_pipeline.py "https://youtube.com/watch?v=xxx" --no-tts
# 或本地文件
python test_pipeline.py /path/to/audio.mp3 --no-tts

# TTS 合成（MiniMax 音质更好）
python tts_minimax.py work/<job_id>

# 开场简介 → final.mp3
python intro_compose.py work/<job_id>

# 生成字幕 + 写入章节
python generate_srt.py work/<job_id>
python add_chapters.py work/<job_id>

# 上传飞书云盘
python upload_feishu.py work/<job_id> --title "节目标题"

# 播放
open work/<job_id>/final.mp3
```

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
| 任务队列（多维表格） | https://m0c4oiqy715.feishu.cn/base/OucDbcF7MaNObBs1WANcmEAQnke |
| 产物云盘文件夹 | https://m0c4oiqy715.feishu.cn/drive/folder/ZEtzfLmtYlsv4Ddoi3WcH0AYnnp |

---

## 文件说明

| 文件 | 作用 |
|------|------|
| `run_jobs.py` | 飞书任务队列轮询，一键跑完整流程 |
| `test_pipeline.py` | 下载 → 转录 → 翻译 |
| `tts_minimax.py` | MiniMax TTS 正文合成 |
| `intro_compose.py` | Claude 生成简介 + TTS → 拼接 final.mp3 |
| `generate_srt.py` | 生成中文 / 双语 SRT 字幕 |
| `add_chapters.py` | 写入 ID3 章节标记 |
| `upload_feishu.py` | 上传产物到飞书云盘 |
| `tts_compose.py` | edge-tts 备用合成 |
| `.env` | API Keys（不提交）`MINIMAX_API_KEY=xxx` |
| `cookies.txt` | YouTube cookies（不提交）|
