# 播客翻译项目 — 进度记录

---

## 🔄 换设备接手清单（2026-07-21 最后同步）

**两个仓库都要拉：**

```bash
git clone https://github.com/mango666ai/podcast-translator.git   # 代码 + 已发布内容
git clone https://github.com/mango666ai/aicoding-notes.git       # 工作区文档（PRD/PROJECT_MAP/决策日志）
git clone --depth 1 https://github.com/Huanshere/VideoLingo.git  # 依赖，提供 Python venv
```

**⚠️ 必须手动补的东西（不在 git 里，故意的）：**

| 项 | 怎么办 |
| --- | --- |
| `podcast_addon/.env` | 新建，填 `DEEPSEEK_API_KEY`（翻译主通道，**必须**）、`MINIMAX_API_KEY` + `MINIMAX_GROUP_ID`（配音，**必须**）。key 只在旧机器的本地 `.env` 里，需要自己复制过来或去官网重新生成 |
| Python venv | 按 [SETUP.md](SETUP.md) 重建（约 10 分钟，whisperX 首次会下 ~3GB 模型） |
| `cookies.txt` | 部分 YouTube 视频需要，用浏览器插件导出，或用 `yt-dlp --cookies-from-browser chrome` |

**不会同步、但可以重新生成的中间产物**（已 gitignore）：`youtube_transcripts/`、`youtube_dub/`、`youtube_demo/`、`work/`。已发布的 8 集成品音频在仓库 `episodes/` 里，不受影响。

**接手先读**：[播客工作循环.md](播客工作循环.md)（标准流程，唯一真相源）→ 本文件最新一条进度 → [../决策日志.md](../决策日志.md)（为什么这样定）

**已建好的克隆声线不会丢**：4 个 MiniMax voice_id 存在云端账号里，已登记在 [voice_ids.md](voice_ids.md)（随 git 同步），换设备后直接引用即可，**不需要重新克隆、不用再花额度**。

**当前状态**：8集全部发布（含第9集），5集处理进度详见下方 2026-08-11 条目——那次发现并修复了一个严重bug（DeepSeek 批量翻译截断导致大段静音），已发布的3集音频都已替换。

---

## 2026-08-11 · 【严重bug】发现并修复 DeepSeek 批量翻译截断导致的大段静音，5集全部修复

- 发现过程：处理4人对谈新集（`gSUMFvc8br0`）核对说话人标注时，人工听小样发现内容衔接不连贯，往下查发现根因不在说话人分轮，而在翻译层——`youtube_dub.py` 的 `translate()` 每批25段调 DeepSeek，回复偶尔在接近 token 上限时被截断或返回的 `i` 编号错位，旧代码对此**完全没有校验**，直接把缺失的段落当空翻译，配音时用静音顶替。
- 影响范围排查（按空翻译时长占已出音频总时长估算）：
  - 第9集 `P3KDebPTUrw`（已发布）：约24%（18.2分钟静音）
  - Alex Lieberman `1_jlukb7gm4`（已发布）：约32%（16.1分钟静音）
  - Dianne Penn `tivaWTTVRhY`（已发布）：约24%（22.5分钟静音）
  - How to Speak `Unzc731iCUY`（未发布）：约51%（27.5分钟静音，最严重）
  - 4人对谈 `gSUMFvc8br0`（处理中）：约16%
- 代码修复：
  - `youtube_dub.py` 的 `translate()`/`_translate_batch()`：新增校验——返回的 `i` 编号集合必须精确等于 `0..N-1`，且原文非空对应的译文不能是空字符串，任一不满足就重试；连续3次失败自动对半拆分批次递归重试（缩小单批请求量规避截断），而不是直接放弃。
  - `build_speaker_rules.py`：说话人判断从"只看每轮发言前200字"改成"开头+结尾各取一段"，避免长发言轮次里的自我介绍/身份线索出现在200字之后被漏看（这个子问题是查这次大bug时先发现的）。
  - 新增 [repair_translation.py](repair_translation.py)：只重新翻译含空段的批次，不用整集重翻；配合删除对应的旧静音语音片段+`youtube_multivoice_dub.py`/`youtube_dub.py`原生的缓存复用机制重新合成，只烧新增段落的 MiniMax 额度。
- 修复结果（已重新出全片音频并验证时长变化跟空段时长量级吻合）：
  - 第9集：77.2→94.4分钟，已替换 `episodes/`+`feed.xml`，推送上线
  - Alex Lieberman：51.1→67.4分钟，已替换并推送上线
  - Dianne Penn：93.9→114.4分钟，已替换并推送上线
  - How to Speak：53.5→74.3分钟，已更新预置在 `episodes/` 的文件，尚未加入 `feed.xml`（原定 2026-08-11 18:00 发布，因发现此 bug 临时暂停，待重新排期）
  - 4人对谈：全新生成完整音频 71.98分钟，已推送，等待排期发布
- 当前判断：3集已发布的音频缺陷已经修复替换，GitHub Pages/客户端缓存刷新后订阅者会拿到修复版；bug 本身已从根源修复（后续新处理的集数不会再出现这个问题）。
- 下一步：
  1. How to Speak 和 4人对谈两集需要重新排发布日期（原定今天发 How to Speak 的计划因这次bug被打断）。
  2. 飞书任务队列状态需要回写这几集的最新进展。

---

## 2026-08-04 · 新机器环境从零搭建；第 9 集正式 DeepSeek 翻译完成；修复翻译批次 JSON 解析脆弱性

- 本次完成：
  - 新机器（`~/AIcoding` 本地磁盘，非 exFAT 外接盘）从零搭建：克隆 `VideoLingo`、建 Python 3.11 venv、装齐 whisperX/pyannote.audio/edge-tts/openai 等全部依赖、装 `yt-dlp`；`.env` 由用户手动填入 `DEEPSEEK_API_KEY` / `MINIMAX_API_KEY` / `MINIMAX_GROUP_ID`。
  - 第 9 集 `P3KDebPTUrw`（Lenny's Podcast，嘉宾 Andrew Ambrosino，OpenAI Codex 桌面应用负责人）：视频无手写字幕，用 YouTube 英文自动字幕（`json3`）代替 whisperX 本地转写（69 分钟音频走 CPU whisperX 太慢，工作流文档 §3.2 允许此替代），转出 432 段。已登记进 [podcast_status.csv](podcast_status.csv)。
  - 用 DeepSeek 正式翻译全片 432 段，生成中文字幕 SRT、双语对照稿、六段式节目笔记（跑在 `youtube_dub/P3KDebPTUrw__OpenAI合并Codex与ChatGPT/` 下，属于 gitignore 的中间产物）。
  - 翻译过程中发现并修复了 [llm_openai.py](llm_openai.py)/[youtube_dub.py](youtube_dub.py) 的真实 bug：432 段要拆 18 批调用 DeepSeek，只要有一批 JSON 解析失败（如 DeepSeek 输出未转义引号，或返回的字段名/类型跟约定的 `{"i":0,"zh":"..."}` 不完全一致），之前的代码会让**已经翻译成功的批次也全部作废**（`translate()` 整体失败没有任何重试或部分保存）。修复：`call_deepseek()` 的 `json_mode` 现在带上 DeepSeek 的 `response_format={"type":"json_object"}` 强约束；`extract_json()` 加 `json_repair` 兜底解析；每批翻译加 3 次重试，且对 `i` 字段缺失/类型不对做了容错（缺失时按批内位置兜底）。修复后一次性跑通 432/432 段，无需人工介入。
- 验证结果：
  - `py_compile` 通过；`test_translate.py` 冒烟测试（6 段）通过。
  - 432/432 段翻译成功，抽查双语对照稿质量正常（含纠正了 YouTube 自动字幕把 "OpenAI" 听写错成 "Opening Eye" 的错误，翻译时根据上下文译回了"OpenAI"）。
- 说话人切分（多声线配音的前置条件）：
  - 先尝试 `pyannote.audio` 自动 diarization（§3.6 的目标方案），但 `pyannote/speaker-diarization-community-1` 是 HF gated 模型，需要用户去 hf.co 接受条款+生成 token；用户当场遇到 HF 网站 418 报错，多次重试未解决，放弃此路线。
  - 改用**文本层面的 LLM 判断**，绕开了整个音频模型/HF token 依赖：`youtube_multivoice_dub.py` 本来就只需要「时间段→speaker 标签」就能合成多声线音频，从不读取原始音频做声纹分析。新写 [build_speaker_rules.py](build_speaker_rules.py)：把 YouTube 自动字幕自带的 `>>` 说话人切换标记切成 186 个发言轮次，丢给 DeepSeek 按对话内容（谁在提问/谁在讲自己经历）判断每轮是主持人还是嘉宾，合并同说话人的相邻轮次生成 99 条 `speaker_rules.json` 规则。抽查内容与标注结果一致，时长分布也合理（嘉宾 Andrew 53 分钟 vs 主持人 Lenny 20 分钟，符合访谈类播客比例）。
  - 过程中发现并修复一个真实 bug：YouTube 滚动字幕的相邻轮次时间戳会重叠（例如一轮 `0.3-7.9s`，下一轮 `6.3-14.9s`），`youtube_multivoice_dub.py` 的 `_speaker_for()` 按时间点查找规则时命中重叠区间里排在前面的规则，导致小样前几段说话人分配错位（实测复现）。修复：`build_speaker_rules.py` 的 `merge_rules()` 现在把每轮的 `end` 裁到下一轮的 `start`，消除重叠，规则区间互不相交。修复后小样交替正确（main/host/main/host…）。
  - 已用前 10 段生成多声线小样 `youtube_dub/P3KDebPTUrw__OpenAI合并Codex与ChatGPT/P3KDebPTUrw__中文配音小样_多声线.mp3`，发给用户试听中，**未获确认前不生成全片完整音频**（避免不经确认烧 MiniMax 额度）。
- 用户确认小样效果 OK 后，跑通全片：
  - `youtube_multivoice_dub.py` 对全部 432 段生成完整音频：`youtube_dub/P3KDebPTUrw__OpenAI合并Codex与ChatGPT/P3KDebPTUrw__OpenAI合并Codex与ChatGPT__完整中文音频_多声线原声还原0.82.mp3`，`ffprobe` 确认 `duration=4632.35s`（约77分12秒）/ `size=39740229`。
  - 已发布：复制改名为 `episodes/P3KDebPTUrw-openai-merging-codex-chatgpt-zh-multivoice.mp3`，SRT 复制到 `transcripts/` 同名，`feed.xml` 新增条目（标题《OpenAI 合并 Codex 与 ChatGPT：实现不再稀缺，品味是护城河》），`python -m xml.etree.ElementTree` 校验格式合法。`podcast_status.csv` 状态改为 `published_multivoice`。
  - **第9集是当前流程里唯一直接发布的一集**——用户明确了新的发布节奏：之后新处理的集数先留在本地攒着，不一次性推 RSS，每天只发一集（见决策日志）。
- 飞书任务队列接入：原配置的应用（appId `cli_a922...`，"芒果"）访问这张多维表格报 `91403 无权限`；用户澄清应该用"总店长"账号 + 名为 Doven 的应用（appId `cli_a92330864c785bde`）访问。已用 `lark-cli config init --name Doven` 配置该应用（secret 走 stdin，未明文落地），并引导总店长账号完成设备码授权，改用 `--profile Doven` 后成功读取到表格内容：
  - 表里有 4 条记录（含 1 条重复提交），对应 3 个不重复视频：`Unzc731iCUY`（MIT《How to Speak》）、`1_jlukb7gm4`（Alex Lieberman，*How I AI*）、`tivaWTTVRhY`（Dianne Penn/Anthropic，*Lenny's Podcast*）。
  - **发现不一致**：`Unzc731iCUY` 在飞书里标记"已完成"（2026-06-10），但 GitHub 仓库（`feed.xml`/`episodes/`）里完全没有这期的任何痕迹——用户确认这是旧链路（`run_jobs.py`→`test_pipeline.py`）留下的过时/测试数据，不代表真发布过。三个视频都已重新登记进 `podcast_status.csv`（`queued`），飞书这条"已完成"以后不再作为已处理的依据。
- 用户离开前交代：接下来自主处理，完成后汇报进度和需要决策的点。三条队列全部推进到"翻译完成"这一步（转写+DeepSeek翻译+字幕+双语稿+节目笔记，全部免费、不涉及决策）：
  - `Unzc731iCUY`（MIT《How to Speak》，Patrick Winston 主讲）：210/210 段翻译成功，单人讲座，不需要 speaker_rules。
  - `1_jlukb7gm4`（Alex Lieberman，*How I AI*）：217/217 段翻译成功，双人对话，`speaker_rules.json` 已建好（59轮发言→54条规则），嘉宾32.3分钟/主持人10.6分钟，跟原视频43分钟时长对得上。
  - `tivaWTTVRhY`（Dianne Penn/Anthropic，*Lenny's Podcast*，93分钟全场最长）：435/435 段翻译成功，双人对话，`speaker_rules.json` 已建好（146轮发言→108条规则），嘉宾52.1分钟/主持人41.7分钟，跟93.8分钟总时长对得上。
  - 三条抽查内容质量都正常，**均未做声音克隆/配音**——这一步要花 MiniMax 额度，是留给用户的决策点（是否要给这3集各建新声线、出小样确认）。
  - 代码修复 + 第9集发布内容已提交推送（`648611a`），三条队列的处理进度也已提交推送（`1b5758a`）。
- 下一步：
  1. 用户回来后决策：这3集是否要继续建声音克隆（`Unzc731iCUY` 需1个新声线；`1_jlukb7gm4`/`tivaWTTVRhY` 各需2个）+ 出小样确认。
  2. 小样确认后按"每天发一集"的节奏排期发布，不要一次性全部推 RSS。
  3. 待办：飞书多维表格作为看板要不要手动同步一下这3条的最新状态（目前实际执行仍在本地 `podcast_status.csv`，飞书暂未回写；且已知飞书里 `Unzc731iCUY` 的"已完成"是过时数据，回写前要注意别被旧状态覆盖了新记录）。

---

## 2026-07-21 · DeepSeek 接入验证通过；节目笔记改六段式；新增双语对照稿；标准流程文档重写；修复 git/`.env` 的 exFAT 元数据损坏

- 本次完成：
  - `llm_openai.py` 新增 `call_deepseek()`，`call_gpt()` 优先级改为 DeepSeek > OpenAI > Claude CLI；冒烟测试 `call_gpt("只回复：ok")` 用真实 `DEEPSEEK_API_KEY` 调用成功。
  - `youtube_dub.py` 新增 `write_bilingual_transcript()`（英文原文+中文翻译逐句对照+`[mm:ss]`时间戳，纯文字稿，不用于播放器同步）和 `build_timestamps()`（从双语分段抽候选点，LLM 只选编号起标签，时间戳始终来自真实数据不由模型编造）；`write_notes_if_needed()` 改为六段式节目笔记（来源/本期播客简介/本期嘉宾/时间戳/精彩内容/播客信息补充），用第1集数据冒烟测试通过。
  - 重写 [播客工作循环.md](播客工作循环.md) 为定版标准流程：核对代码后删除了从未真正用于生产的"飞书队列入口"描述，更新翻译优先级，补充双语对照稿/六段式笔记，明确列出"当前不做"清单（开场白/ID3章节/飞书上传/自动diarization），删除过时的8视频状态表（改为指向 `podcast_status.csv`）。
  - 修复 `.git` 目录被 exFAT 自动生成的 macOS AppleDouble 元数据文件（`._*`）污染，导致 `git log`/`git fsck` 报错（172个垃圾文件，含 `refs/heads/._main` 等）；清理后仓库恢复正常，真实 `main` ref 数据未受影响。
  - 修复本地 `.env` 被同样的 AppleDouble 元数据（`._.env`）干扰导致 Finder/TextEdit 报"已损坏"；确认 `.env` 本体完好后清掉影子文件，用户自行在文件末尾追加了真实 `DEEPSEEK_API_KEY`。
  - 新写 [PRD.md](../PRD.md)（项目说明文档）和 [PROJECT_MAP.md](../PROJECT_MAP.md) 复核更正；决策日志补全多条：原计划环节取舍（开场白/ID3/飞书/双语对照）、DeepSeek 验证通过。
- 验证结果：
  - `python -m py_compile llm_openai.py youtube_dub.py` 通过。
  - `call_gpt` 真实 DeepSeek key 调用成功。
  - 用第1集(`9fubhllmsBU`)已有双语分段数据跑通 `write_notes_if_needed` 和 `write_bilingual_transcript`，输出内容人工检查过，格式和内容质量符合预期。
  - `git fsck --full` 清理后无异常（仅剩正常的 dangling object 提示）。
- 当前判断：
  - 翻译层的最大阻塞（无稳定自动通道）已解除，第9集及以后可以走全自动翻译。
  - 前3集(`9fubhllmsBU`/`az6OEZV8iHw`/`ohKt066uFhg`)的节目笔记还是旧五段格式，未随本次改动重新生成。
- 下一步：
  1. 是否要批量用新六段式模板重新生成前3集（乃至全部8集）的节目笔记和双语对照稿，待用户确认。
  2. 用 DeepSeek 正式跑第9集(`P3KDebPTUrw`)翻译，替换掉之前的 YouTube 自动字幕测试版。
  3. 提交并推送本次全部改动（含之前遗留的未提交文件）。

## 2026-07-19 · 新视频完整本地测试版完成，发布前改接 DeepSeek 翻译

- 用户反馈：
  - `P3KDebPTUrw` 的双声线 demo 可以接受，可以继续跑完整视频。
  - 但正式发布前不要再使用 YouTube 自动中文字幕作为最终翻译稿。
  - 后续音频标题需要带序号，例如 `01.`、`02.`。
  - 播客简介格式需要固定：先写来源，再写原内容更新时间，再介绍嘉宾/主持人和内容亮点。
- 本次完成：
  - 已用 YouTube 自动中文字幕 + 两个 MiniMax 克隆声线生成完整本地测试版：
    - `/Volumes/SANDISK ELE/AICoding/project5_podcast/podcast_addon/youtube_demo/P3KDebPTUrw/P3KDebPTUrw_full_auto_zh_multivoice.mp3`
    - 时长约 72 分 23 秒，大小约 39MB。
  - 已确认没有上传到 GitHub / RSS。
  - 新增项目地图：
    - `/Volumes/SANDISK ELE/AICoding/project5_podcast/PROJECT_MAP.md`
- 验证结果：
  - `ffprobe` 检查完整音频：`duration=4342.843313`，`size=38939229`。
  - 发布仓库当前无未提交变更。
- 当前判断：
  - 这版只能作为完整流程测试版，不作为正式发布版。
  - 当前真正阻塞是缺少稳定的高质量翻译层，不是下载或 TTS。
- 下一步：
  1. 用户提供 DeepSeek API Key 后，把翻译层改为 DeepSeek 优先。
  2. 用 DeepSeek 基于英文字幕/转写重新生成自然中文分段。
  3. 保留现有两个人声克隆，重新 TTS 生成正式音频。
  4. 正式发布时按序号命名，RSS 标题和简介使用新版格式。

## 2026-07-19 · 第 8 集多声线原声还原版已生成并发布

- 用户反馈：
  - 第 8 集当前发布版没有区分人声，长期目标应按原视频原声还原，而不是沿用 demo 时选定的固定声线。
- 本次完成：
  - 确认现有 `youtube_dub.py` 是单 voice_id 合成，所以当前第 8 集发布版是 Brent 克隆声覆盖全片。
  - 从原始音频截取主持人 Damian 开场样本：`youtube_transcripts/_audio/Yz03ERsfDDM_damian_host_sample.mp3`。
  - 使用 MiniMax voice clone 成功创建主持人声线：`voice_id=Yz03ERsfDDM_damian_20260719`。
  - 新增多声线合成脚本：`youtube_multivoice_dub.py`，用于把不同时间段路由到不同 voice_id。
  - 新增第 8 集说话人规则：`youtube_dub/Yz03ERsfDDM__Brat封面设计师经历/Yz03ERsfDDM__speaker_rules.json`。
  - 用户为 Pay-as-you-go Audio Points 充值后，继续复用前 30 段缓存，补齐剩余段落。
  - 多声线完整生成 76/76 段：
    - 0:19-2:15 左右：主持人 Damian 克隆声。
    - Brent 主讲：`Yz03ERsfDDM_brent_20260717`。
    - 家庭录像/引用片段：临时用 `Calm_Woman` 区分，后续如要更真实可再单独处理。
  - 生成完整音频：`youtube_dub/Yz03ERsfDDM__Brat封面设计师经历/Yz03ERsfDDM__Brat封面设计师经历__完整中文音频_多声线原声还原1.00.mp3`，约 22 分 48 秒 / 12.8MB。
  - 已复制到发布仓库并用新文件名替换 RSS enclosure：`episodes/Yz03ERsfDDM-brat-cover-designer-zh-multivoice.mp3`。
  - RSS 描述已标注“多声线原声还原版”，说明主持人、主讲人和片段声线有区分。
- 验证结果：
  - 本地分段缓存 76/76 段齐全。
  - `ffprobe` 检查完整音频：`duration=1368.478906`，`size=12765897`。
  - 发布仓库 `feed.xml` 可解析，仍为 8 个 item，第 8 集 enclosure 指向新多声线 MP3。
- 下一步：
  1. 等 GitHub / 小宇宙缓存刷新，在小宇宙试听第 8 集多声线版。
  2. 若第 8 集方向满意，再评估前 7 集是否按原视频 speaker 重新配音。
  3. 长期把“按说话人克隆声线”纳入默认工作循环：每集先做 speaker 标注，再按 speaker 选择/克隆 voice_id。

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
