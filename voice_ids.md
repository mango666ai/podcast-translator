# MiniMax 克隆声线登记表

> 每个 voice_id 都是花 MiniMax 额度克隆出来的，**存在 MiniMax 云端账号里，不随本地文件走**。
> 换设备后这些 id 仍然可用，直接在 `youtube_multivoice_dub.py --main-voice <voice_id>` 里引用即可，不需要重新克隆。
> 本地的 `*_voice_clone.json`（含完整 API 响应）在 gitignore 的目录里，不会同步；这份表是唯一随 git 走的记录。

| voice_id | 对应人物 | 所属集 | 创建日期 | 参考音频来源 |
| --- | --- | --- | --- | --- |
| `Yz03ERsfDDM_brent_20260717` | Brent David Freaney（主讲人） | 第8集 Brat封面设计师经历 | 2026-07-17 | 原视频 Brent 演讲段，约 2 分钟 |
| `Yz03ERsfDDM_damian_20260719` | Damian（主持人） | 第8集 Brat封面设计师经历 | 2026-07-19 | 原视频开场主持段 |
| `P3KDebPTUrw_host_20260719` | Lenny（主持人，*Lenny's Podcast*） | 第9集（`P3KDebPTUrw`，已发布） | 2026-07-19 | 原视频主持段 |
| `P3KDebPTUrw_andrew_20260719` | Andrew Ambrosino（嘉宾） | 第9集（`P3KDebPTUrw`，已发布） | 2026-07-19 | 原视频嘉宾段 |
| `Unzc731iCUY_winston_20260805` | Patrick Winston（主讲人，MIT教授） | `Unzc731iCUY` How to Speak（单人讲座） | 2026-08-05 | 原视频 320-410s 讲座片段，90秒 |
| `v1jlukb7gm4_host_20260805` | How I AI 播客主持人 | `1_jlukb7gm4` Alex Lieberman访谈 | 2026-08-05 | 原视频 1290-1380s 主持段，90秒 |
| `v1jlukb7gm4_alex_20260805` | Alex Lieberman（嘉宾） | `1_jlukb7gm4` Alex Lieberman访谈 | 2026-08-05 | 原视频 760-850s 嘉宾段，90秒 |
| `tivaWTTVRhY_dianne_20260805` | Dianne Penn（嘉宾，Anthropic） | `tivaWTTVRhY` Dianne Penn访谈 | 2026-08-05 | 原视频 2680-2770s 嘉宾段，90秒 |
| （复用）`P3KDebPTUrw_host_20260719` | Lenny（主持人） | `tivaWTTVRhY` Dianne Penn访谈 | — | 同一主持人，复用第9集已克隆声线，未新建 |
| `gSUMFvc8br0_host_20260811` | Nuel Singhal（主持人，*The Skip*） | `gSUMFvc8br0` 三位产品负责人的AI一线心法（4人对谈） | 2026-08-11 | 原视频 449-529s 主持段，80秒 |
| `gSUMFvc8br0_sharmeen_20260811` | Sharmeen Chapp（Midjourney首位产品岗） | `gSUMFvc8br0` 三位产品负责人的AI一线心法（4人对谈） | 2026-08-11 | 原视频 20-110s 嘉宾段，90秒 |
| `gSUMFvc8br0_jz_20260811` | Jiaona Zhang（Laurel CPO） | `gSUMFvc8br0` 三位产品负责人的AI一线心法（4人对谈） | 2026-08-11 | 原视频 1830-1920s 嘉宾段，90秒 |
| `fWa7uxyhVDE_michael_20260819` | Michael Truell（Cursor/Anysphere联合创始人兼CEO） | `fWa7uxyhVDE` Cursor开场主题演讲 | 2026-08-19 | 原视频 30-120s 开场段，90秒 |
| `fWa7uxyhVDE_kevin_20260819` | Kevin（Cursor团队成员） | `fWa7uxyhVDE` Cursor开场主题演讲 | 2026-08-19 | 原视频 810-900s 段落，90秒 |
| `fWa7uxyhVDE_tamas_20260819` | Tamas/Thomas（Cursor团队成员，字幕拼写不一致） | `fWa7uxyhVDE` Cursor开场主题演讲 | 2026-08-19 | 原视频 1180-1270s 段落，90秒 |
| `gSUMFvc8br0_henrik_20260811` | Henrik Berggren（Mutiny产品设计负责人） | `gSUMFvc8br0` 三位产品负责人的AI一线心法（4人对谈） | 2026-08-11 | 原视频 790-880s 嘉宾段，90秒 |
| `ByOF8qByGHU_farhan_20260821` | Farhan Thawar（Shopify工程负责人，单人演讲） | `ByOF8qByGHU` 工程师现在的工作是什么 | 2026-08-21 | 原视频 60-150s 段，90秒 |

## 命名约定

```
<video_id>_<人物英文名或角色>_<YYYYMMDD>
```

⚠️ MiniMax 要求 `voice_id` **首字符必须是字母**。如果 `video_id` 本身是数字开头（如 `1_jlukb7gm4`），克隆会报 `2013 invalid params, voice_id first character`，需要加个字母前缀（如 `v1jlukb7gm4_...`），见下方 `v1jlukb7gm4_*` 两条。

## 新建声线

```bash
python clone_minimax_voice.py <参考音频.mp3> \
  --voice-id <video_id>_<角色>_<YYYYMMDD> \
  --out <输出json路径>
```

参考音频要求：1-2 分钟、该人物单独说话、尽量无背景音乐/掌声。建好后**必须回来更新这张表**。

## 注意

- 预置音色（`Wise_Woman`/`Calm_Woman`/`Elegant_Man` 等）只能用于临时 demo，正式发布一律用原声克隆，见 [播客工作循环.md](播客工作循环.md) §3.6。
- 第 8 集里"家庭录像/引用片段"当时临时用了预置音色 `Calm_Woman` 区分，属于待改进项。
