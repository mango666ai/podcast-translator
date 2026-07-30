# MiniMax 克隆声线登记表

> 每个 voice_id 都是花 MiniMax 额度克隆出来的，**存在 MiniMax 云端账号里，不随本地文件走**。
> 换设备后这些 id 仍然可用，直接在 `youtube_multivoice_dub.py --main-voice <voice_id>` 里引用即可，不需要重新克隆。
> 本地的 `*_voice_clone.json`（含完整 API 响应）在 gitignore 的目录里，不会同步；这份表是唯一随 git 走的记录。

| voice_id | 对应人物 | 所属集 | 创建日期 | 参考音频来源 |
| --- | --- | --- | --- | --- |
| `Yz03ERsfDDM_brent_20260717` | Brent David Freaney（主讲人） | 第8集 Brat封面设计师经历 | 2026-07-17 | 原视频 Brent 演讲段，约 2 分钟 |
| `Yz03ERsfDDM_damian_20260719` | Damian（主持人） | 第8集 Brat封面设计师经历 | 2026-07-19 | 原视频开场主持段 |
| `P3KDebPTUrw_host_20260719` | 主持人 | 第9集（`P3KDebPTUrw`，未发布） | 2026-07-19 | 原视频主持段 |
| `P3KDebPTUrw_andrew_20260719` | Andrew（嘉宾） | 第9集（`P3KDebPTUrw`，未发布） | 2026-07-19 | 原视频嘉宾段 |

## 命名约定

```
<video_id>_<人物英文名或角色>_<YYYYMMDD>
```

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
