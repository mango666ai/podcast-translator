# Codex 播客工作手册

> 给接手本项目的 Codex 使用。标准业务流程仍以《播客工作循环.md》为准；本文件定义代理必须遵守的执行门禁。

## 开工

1. `git pull`，检查分支、`git status`、最近提交。
2. 完整阅读 `AGENTS.md`、`PRD_SUMMARY.md`、`播客工作循环.md`、`PROGRESS.md`；返修时再读 `技术债.md`。
3. 一次只推进一集。`run_jobs.py` 是旧链路，禁止当作生产入口。
4. 先确认本轮是“新制作、返修、入 staging、转正式”中的哪一种，不把计划当成已完成。

## 制作门禁

1. 英文自动字幕可作输入；自动中文字幕不能作正式译稿。
2. 翻译完成后先运行：

   ```bash
   python3 audit_translation.py <双语分段.json> --strict
   ```

   自动审计只能发现高风险片段，不能证明语义对应；警告必须逐条复核，且至少抽看开头、中段、结尾和所有异常区间。
3. 返修旧节目时禁止传 `--trust-legacy-cache`。无 `.txt` 指纹的分段缓存一律视为不可信。
4. 合成后核对：分段数、指纹数、ffmpeg 成品时长、字幕末尾时间；文件出现不代表 ffmpeg 已写完。
5. 多说话人节目检查 `>>` 轮次规则；送入 TTS 和 SRT 的文本都必须经过 `clean_for_tts()`。

## 发布门禁

1. 只用 `stage_episode.py` 入待审，只用 `publish_from_staging.py` 转正式，禁止手改 RSS 拼发布。
2. staging 必须人工试听后才能转正式；敏感或放弃内容要同时从 feed、公开 MP3/SRT 和状态表撤下。
3. 发布前后都运行 `python3 podcast_doctor.py`；每集单独 commit、push，并检查远端 URL。
4. 一次性发布时间不能伪装成 Codex 的每日自动任务。Codex 自动化是重复调度；本项目默认到点人工执行，或使用明确支持一次性触发且已验证权限的机制。
5. 无人值守前必须先手动跑通同一命令并完成权限授权；任务要可重复执行而不产生重复条目。

## 四集存量返修顺序

1. `P3KDebPTUrw`：当前 JSON 可作基准，但旧音频混入无指纹缓存；整集重新合成最稳妥，禁止信任旧缓存。
2. `tivaWTTVRhY`：先重译并人工核对约 `#154–#173` 的整批，再重建对应音频。
3. `ByOF8qByGHU`：先重译并人工核对覆盖 `#83–#100` 的完整翻译批次，再重建对应音频。
4. `zxvyO5vnknI`：已于 2026-10-08 完成试点返修；实际除 `#89/#92` 外，审计还发现 `#28–#35` 整段扩写，最终重译第 2、4 批并整集重合成。

每集返修后：重写 SRT → 合成/拼接 → 抽听异常区间前后各两段 → 替换正式 MP3/SRT → `podcast_doctor.py` → 单独 commit/push。

## 历史事故与防线

| 事故 | 防线 |
| --- | --- |
| DeepSeek 输出截断/漏段 | 编号、非空、echo 检查；失败拆批重试 |
| echo 正确但中文批内错位 | `audit_translation.py` + 异常区间人工 EN/ZH 对照；不把 echo 当语义证明 |
| 只按序号命中旧 TTS 缓存 | 文本/voice/speed 指纹；返修禁用 legacy cache |
| `>>`、音乐/笑声标记被念出 | `clean_for_tts()` 作为统一入口 |
| CosyVoice WebSocket 永久挂起 | 120 秒超时和重试 |
| 24k/32k 混拼静默截断 | 统一采样参数 + 成品时长校验 |
| ffmpeg 尚未写完就复制 | `wait_until_stable()` |
| staging MP3 被 gitignore 导致死链 | 跟踪 staging 成品 + `podcast_doctor.py` + 远端检查 |
| 手改 RSS 漏换 staging URL | 只用发布脚本 |
| 无人值守任务卡权限弹窗 | 先 Run Now/手动预授权；失败不视为完成 |

## 收工

更新 `PROGRESS.md`；如形成产品/技术/范围决策，写上一级私有 `决策日志.md`（日期、结论、why）。按项目规则 commit、push，并明确汇报未完成项。
