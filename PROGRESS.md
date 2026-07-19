# 播客翻译项目 — 进度记录

## 2026-07-19 · 第 8 集改做多声线原声还原，卡在 MiniMax 额度

- 用户反馈：
  - 第 8 集当前发布版没有区分人声，长期目标应按原视频原声还原，而不是沿用 demo 时选定的固定声线。
- 本次完成：
  - 确认现有 `youtube_dub.py` 是单 voice_id 合成，所以当前第 8 集发布版是 Brent 克隆声覆盖全片。
  - 从原始音频截取主持人 Damian 开场样本：`youtube_transcripts/_audio/Yz03ERsfDDM_damian_host_sample.mp3`。
  - 使用 MiniMax voice clone 成功创建主持人声线：`voice_id=Yz03ERsfDDM_damian_20260719`。
  - 新增多声线合成脚本：`youtube_multivoice_dub.py`，用于把不同时间段路由到不同 voice_id。
  - 新增第 8 集说话人规则：`youtube_dub/Yz03ERsfDDM__Brat封面设计师经历/Yz03ERsfDDM__speaker_rules.json`。
  - 多声线生成已跑通前 30/76 段：
    - 0:19-2:15 左右：主持人 Damian 克隆声。
    - Brent 主讲：`Yz03ERsfDDM_brent_20260717`。
    - 家庭录像/引用片段：临时用 `Calm_Woman` 区分，后续如要更真实可再单独处理。
- 阻塞项：
  - MiniMax 返回 `insufficient credit. Please purchase top-up credits or upgrade your subscription plan`，第 31 段开始无法继续合成。
  - 因此完整多声线版尚未生成，也未替换 RSS；小宇宙当前看到的仍是已发布的单声线 Brent 克隆版。
- 下一步：
  1. 补足 MiniMax TTS 额度或换可用 TTS 供应商。
  2. 继续运行多声线合成脚本，剩余段落会复用已生成缓存，从第 31 段附近继续。
  3. 生成完整 `__完整中文音频_多声线原声还原1.00.mp3` 后，复制到发布仓库，用新 MP3 文件名替换 RSS 第 8 集 enclosure，再提交并推送 GitHub。
  4. 长期把“按说话人克隆声线”纳入默认工作循环：每集先做 speaker 标注，再按 speaker 选择/克隆 voice_id。

## 2026-07-17 · 第 8 集补齐：原视频声线克隆版已发布

- 本次完成：
  - 用户授权后，使用 Chrome cookies 成功下载 `Yz03ERsfDDM` 原视频音频：`youtube_transcripts/_audio/Yz03ERsfDDM.mp3`（约 18MB）。
  - 本地 whisper/faster-whisper 转写在 CPU 上耗时长且不稳定，改用 YouTube 自动英文字幕 `Yz03ERsfDDM.en.vtt` 清洗为 `youtube_transcripts/Yz03ERsfDDM.json/txt`。
  - 手动补齐中文双语分段：`youtube_dub/Yz03ERsfDDM__Brat封面设计师经历/...__双语分段.json`。
  - 从原视频 Brent 开始演讲后的片段截取 2 分钟人声样本：`Yz03ERsfDDM_brent_clone_sample.mp3`。
  - 使用 MiniMax voice clone 创建原视频声线克隆：`voice_id=Yz03ERsfDDM_brent_20260717`。
  - 使用克隆声线生成完整中文音频：约 22 分 51 秒 / 12.9MB，无异常小片段。
  - 已复制到发布仓库并更新 RSS，新条目标题：`Brat 封面设计师经历：没有完成状态的设计`。
- 当前状态：
  - 8 个视频全部已进入 RSS / GitHub。
  - 第 8 集是第一条“原视频声线克隆版”；前 7 集仍是 demo 固定声线版本。
- 下一步建议：
  1. 先在小宇宙试听第 8 集声线克隆效果。
  2. 若满意，再批量为前 7 集提取原声样本、创建 voice_id，并重配音替换 RSS。
  3. RSS 描述中继续明确标注“AI 中文译制版 / 使用原视频声线克隆”，避免听众误解为原讲者本人录制中文。

## 2026-07-17 · 夜间批处理：7 集已进入 RSS，最后 1 集卡 YouTube 登录校验

- 当前总状态：
  - 已完整生成中文音频并发布到 GitHub/RSS 的 7 集：
    1. `9fubhllmsBU` · `Fable5提示词最佳实践`
    2. `ohKt066uFhg` · `Slack里的AI员工`
    3. `az6OEZV8iHw` · `Cursor界面改版设计`
    4. `l5VRhrNeidY` · `AI时代面向人类写作`
    5. `4CAFK-rc26A` · `AI时代PM职能演化`
    6. `otkSbl399tU` · `2000年代设计灵感`
    7. `u7_Qof3AJ1g` · `Notion设计系统落地`
  - 仍未完成的 1 集：
    1. `Yz03ERsfDDM` · `Brat封面设计师经历`
- 本次完成：
  - 修复 Claude CLI 本地配置：`~/.claude/settings.json` 里残留的 `ANTHROPIC_*` 覆盖项会导致 connectors 被禁用；已备份并移除，`claude -p "只回复 ok" --model sonnet` 一度可返回 `ok`。
  - 但 Claude CLI 后续稳定返回 `403 Request not allowed`，无法作为脚本批量翻译后端；本次改由当前 Codex 对话直接补齐中文双语分段文件，再调用 MiniMax TTS。
  - 为 4 集未完成视频补齐 `__双语分段.json`、生成 `__中文字幕.srt`、完整中文音频：
    - `l5VRhrNeidY`：约 24 分 51 秒 / 15.2MB
    - `4CAFK-rc26A`：约 27 分 12 秒 / 16.6MB
    - `otkSbl399tU`：约 20 分 52 秒 / 12.9MB
    - `u7_Qof3AJ1g`：约 23 分 29 秒 / 14.4MB
  - `youtube_dub.py` 已增加 MiniMax TTS 自动重试逻辑：网络抖动时先重试，不再直接写入静音占位。
  - 4 集新音频、字幕、shownotes 已复制到发布仓库 `/Users/dove/Documents/Codex/2026-07-11/new-chat/work/podcast-translator`，RSS 已新增 4 个条目并推送 GitHub。
  - GitHub commit：`96ef077 Publish four translated podcast episodes`。
  - 已验证远端 raw feed：`https://raw.githubusercontent.com/mango666ai/podcast-translator/main/feed.xml` 现在有 7 个 item。
- 阻塞项：
  - `Yz03ERsfDDM` 无本地音频/转写。无 cookies 下载和只抓自动字幕都被 YouTube 拦截：`Sign in to confirm you’re not a bot`。
  - 当前未授权读取 Chrome cookies，项目内也没有 `cookies.txt`，因此这一集无法继续下载/转写。
- 明天下一步：
  1. 在小宇宙检查 RSS 是否已同步到 7 集；GitHub Pages 和小宇宙可能有缓存，raw feed 已确认更新。
  2. 试听新 4 集，重点听语速、开头、是否有明显断句问题。
  3. 对 `Yz03ERsfDDM`：用户手动导出 YouTube cookies 到 `cookies.txt`，或直接提供音频文件；随后重跑 `youtube_transcribe.py --lang en --only Yz03ERsfDDM`。
  4. 若继续依赖本地 Claude CLI 批量翻译，需要解决 `403 Request not allowed`；否则继续使用 OpenAI API Key 方案或由 Codex 对话补分段。

## 2026-07-16 · 接手摘要：3 集已发布，剩余批处理卡在 LLM 自动调用

- 当前总状态：
  - 已完整生成并发布到 RSS / 小宇宙源的 3 集：
    1. `9fubhllmsBU` · `Fable5提示词最佳实践`
    2. `ohKt066uFhg` · `Slack里的AI员工`
    3. `az6OEZV8iHw` · `Cursor界面改版设计`
  - 已有英文转写、已补来源与简介草稿，但尚未翻译/配音的 4 集：
    1. `l5VRhrNeidY` · `AI时代面向人类写作`
    2. `4CAFK-rc26A` · `AI时代PM职能演化`
    3. `otkSbl399tU` · `2000年代设计灵感`
    4. `u7_Qof3AJ1g` · `Notion设计系统落地`
  - 尚未完成下载/转写的 1 集：
    1. `Yz03ERsfDDM` · `Brat封面设计师经历`
- 本次完成：
  - `podcast_status.csv` 已新增并填写 `source` 字段，所有 8 集都记录了大会/频道来源。
  - 已发布 3 集的 shownotes 已补 `## 来源` 小节。
  - 为 4 集未翻译视频生成了 `__简介与亮点.md` 草稿，均包含来源信息。
  - `u7_Qof3AJ1g` 实际已存在英文转写，状态已从 `downloaded` 修正为 `transcribed`。
  - `llm_openai.py` 已改为：若存在真实 `OPENAI_API_KEY` 则走 OpenAI；否则 fallback 到本地 Claude CLI。
- 验证结果：
  - `../VideoLingo/.venv/bin/python -m py_compile llm_openai.py youtube_dub.py test_pipeline.py intro_compose.py test_translate.py` 已通过。
  - `test_translate.py` 进入 LLM 调用路径后，因无真实 OpenAI API Key fallback 到 Claude CLI；Claude CLI 使用 `sonnet/fable/opus` 极短请求均长时间无返回，`test_translate.py` 120 秒超时。
  - 当前 `.env` 没有真实 OpenAI API Key；用户确认“不想配置 API Key，只想用账号/Claude Code 这类本地能力继续”。
- 阻塞项：
  - 自动翻译/简介生成依赖 LLM 调用；当前 OpenAI API Key 不可用，Claude CLI 又超时无返回，因此无法继续自动生成第 4 集以后完整中文音频。
  - `Yz03ERsfDDM` 昨晚尝试启动 `youtube_transcribe.py --only Yz03ERsfDDM`，会话中断后未看到 `youtube_transcripts/Yz03ERsfDDM.txt/json` 或 `_audio/Yz03ERsfDDM.mp3` 产物，需要重跑确认是否被 YouTube 反机器人拦截。
- 下一步建议给 Claude Code：
  1. 先修复/验证 Claude CLI：运行 `claude -p "只回复 ok" --model sonnet`。若仍超时，先让用户重新登录或检查 Claude Code 网络/订阅状态。
  2. Claude CLI 可用后，运行：`../VideoLingo/.venv/bin/python youtube_dub.py l5VRhrNeidY --speed 1.00`，然后按顺序处理 `4CAFK-rc26A`、`otkSbl399tU`、`u7_Qof3AJ1g`。
  3. 每集完成后更新 `podcast_status.csv`：`translated=yes`、`notes=yes`、`full_tts=yes`，最终发布后标记 `published=yes`。
  4. 重跑 `../VideoLingo/.venv/bin/python youtube_transcribe.py --lang en --only Yz03ERsfDDM`，补齐最后一集英文转写。
  5. 发布新集时继续使用当前 RSS 方案：RSS 放在 GitHub Pages，音频 enclosure 使用已验证可访问的 `raw.githubusercontent.com` 链接。

## 2026-07-15 · 切换到 OpenAI GPT + 来源字段

- 本次完成：`youtube_dub.py`、`test_pipeline.py`、`intro_compose.py`、`test_translate.py` 已从 Claude CLI 改为直接调用 OpenAI GPT；新增 `llm_openai.py` 统一读取 `OPENAI_API_KEY` / `OPENAI_MODEL`。`podcast_status.csv` 新增 `source` 字段，前 3 集已标记 `published`，已生成的 shownotes 补入“来源”小节。
- 验证结果：用 VideoLingo venv 语法检查通过；`test_translate.py` 能正常进入 GPT 调用路径，但当前 `.env` 缺少 `OPENAI_API_KEY`，因此实际 API 调用被明确阻断。
- 下一步：在 `.env` 添加 `OPENAI_API_KEY`（可选 `OPENAI_MODEL=gpt-5.6-luna`），然后继续处理 `l5VRhrNeidY` 及剩余视频。
- 阻塞项：缺 OpenAI API Key，无法继续批量翻译和生成新 shownotes。

## 2026-07-12 · 工作区收工规则

- 本次完成：补充 AGENTS.md，收工时强制检查决策日志并更新本文件。
- 验证结果：文档规则已写入；本次未运行转写/配音测试。
- 下一步：继续验证当前 YouTube 配音与小宇宙端到端流程。
- 阻塞项：小宇宙下载的 cookie/鉴权问题；当前仓库存在用户未提交的配音工作文件，本次未触碰。

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
| 任务队列（多维表格） | https://m0c4oiqy715.feishu.cn/base/OucDbcF7MaNObBs1WANcmEAQnke |
| 云盘文件夹 | 播客翻译 |
| folder_token | `ZEtzfLmtYlsv4Ddoi3WcH0AYnnp` |
| 文件夹链接 | https://m0c4oiqy715.feishu.cn/drive/folder/ZEtzfLmtYlsv4Ddoi3WcH0AYnnp |

## 技术链路（当前完整版）

```
音频输入（YouTube / RSS / 本地）
  → yt-dlp 下载                                ✅
  → whisperX 转录（large-v3，CPU int8）         ✅
  → pyannote 说话人分离（diarization）          ← 待接入（M2）
  → LLM 翻译（OpenAI API 或 Claude CLI fallback）← 当前阻塞：无 OpenAI Key，Claude CLI 超时
  → MiniMax TTS 正文合成（逐段）               ✅ → output_zh_minimax.mp3
  → LLM 生成开场简介 + MiniMax TTS             ← 同上，依赖 LLM 调用恢复
  → ffmpeg 拼接 intro + 正文                   ✅ → final.mp3
  → generate_srt.py 生成字幕                   ✅ → .srt
  → add_chapters.py 写入 ID3 章节              ✅
  → upload_feishu.py 上传飞书云盘              ✅
  ── 后期 ──
  → F5-TTS 跨语言声音克隆                      ← M3
```

---

## 当前进度（截至 2026-06-09）

### ✅ 已完成

| 步骤 | 说明 |
|------|------|
| 环境搭建 | VideoLingo/.venv，Python 3.11.15，含 mutagen / edge-tts / whisperX 等全部依赖 |
| whisperX 转录 | large-v3，Mac CPU / int8，已验证 |
| OpenAI GPT 翻译 | 意译质量好，JSON 解析稳定，支持断点续跑 |
| `test_pipeline.py` | 完整链路：下载 → 转录 → 翻译，支持断点续跑、cookies.txt |
| `tts_compose.py` (M1) | edge-tts 逐段合成 + ffmpeg 拼接 → `output_zh.mp3` |
| `tts_minimax.py` | MiniMax TTS 合成，已跑通 → `output_zh_minimax.mp3`，含 `--preview` 试听模式 |
| `intro_compose.py` (M4) | Claude 生成简介 → MiniMax/edge-tts → intro.mp3 → 拼接为 final.mp3 |
| `generate_srt.py` (M5a) | 从 bilingual.json 生成中文 + 双语 SRT 字幕 |
| `add_chapters.py` (M5c) | 写入 ID3 CHAP 章节标记（mutagen），Overcast / Pocket Casts 可跳转 |
| `upload_feishu.py` | 自动上传 MP3 + SRT 到飞书云盘「播客翻译」文件夹，记录上传结果 |
| **端到端全流程试跑** | YouTube → 转录 → 翻译 → TTS → 简介 → 字幕 → 章节 → 飞书，全部跑通 ✅ |
| `run_jobs.py` | 飞书多维表格任务队列轮询，`--loop` 模式持续监听，一键跑完整流程 |
| 飞书多维表格 | 播客任务队列建好，含提交表单（待处理/处理中/已完成/失败） |
| README.md | 写好开机运行步骤，文件说明，飞书链接 |

### 🔧 本次修复（2026-06-08 全流程试跑中发现）

| 问题 | 修复 |
|------|------|
| 翻译 JSON 解析偶发失败 | `extract_json` 加入 `json_repair` 容错，不再硬 crash |
| MiniMax voice ID 报错 | 国际版不支持 `Podcast_female` 等，改用 `Wise_Woman`/`Calm_Woman` 等英文 ID |
| 翻译模型入口 | 已改为直接调用 OpenAI GPT，避免 Claude CLI 模型退休/配额问题 |

### 🔄 下一步（优先级排序）

1. **验证 run_jobs.py**：用飞书表单提交一条真实任务，跑通完整自动化流程
2. **完整集处理**：跑一整集（30-60 分钟），验证长音频稳定性和耗时
3. **M2**：接入 diarization 多说话人分音色（需 HuggingFace token）
4. **M3**：F5-TTS 跨语言声音克隆

### ⏳ 里程碑

| 里程碑 | 状态 | 内容 |
|--------|------|------|
| M0 | ✅ | 下载 + 转录 + 翻译 pipeline |
| M1 | ✅ | edge-tts + ffmpeg → output_zh.mp3 |
| M4 | ✅ 验证 | OpenAI GPT 简介 + MiniMax TTS → intro.mp3 → final.mp3 |
| M5a | ✅ 验证 | SRT 字幕（中文 + 双语） |
| M5b | ✅ | 双语 .md 已有 |
| M5c | ✅ 验证 | ID3 章节标记（mutagen） |
| 飞书上传 | ✅ 验证 | 自动上传到飞书云盘「播客翻译」 |
| 任务队列 | ✅ 代码完成 | 飞书表单 → run_jobs.py → 自动处理 → 回写状态（待实测）|
| M2 | ⏳ | 多 speaker 分音色（接入 diarization） |
| M3 | ⏳ | F5-TTS 跨语言声音克隆 |

---

## 已知问题 & 解决方案

| 问题 | 解决方案 |
|------|---------|
| YouTube bot 检测 | 把 cookies.txt 放项目根目录自动识别；或用 RSS 直链 |
| torchcodec warning（pyannote import 时） | 无害，自动 fallback soundfile，忽略即可 |
| OpenAI 模型 | 默认 `gpt-5.6-luna`；可用 `OPENAI_MODEL` 覆盖 |
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
├── intro_compose.py     # M4: OpenAI GPT 简介 + TTS → intro.mp3 → final.mp3
├── generate_srt.py      # M5a: 生成 SRT 字幕（中文 + 双语）
├── add_chapters.py      # M5c: 写入 ID3 章节标记
├── upload_feishu.py     # 上传产物到飞书云盘「播客翻译」文件夹
├── run_jobs.py          # 🆕 飞书任务队列轮询，开机运行这个就够
├── README.md            # 🆕 开机运行步骤 + 文件说明
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
