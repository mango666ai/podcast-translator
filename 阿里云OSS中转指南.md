# 阿里云 OSS 音频中转指南（为 CosyVoice 声音复刻铺路）

**为什么需要这一步**：2026-09-02 实测确认，阿里云百炼 CosyVoice 的声音复刻接口**不接受 base64 音频**，
只接受一个 `url`；而且这个 URL **必须能被阿里云内网侧访问到**——用 `raw.githubusercontent.com` 会直接返回
`download audio failed`。所以需要一个国内可达的音频落脚点，OSS 是成本最低、最标准的做法。

> 本文只解决「怎么把一段参考音频变成一个阿里云能下载的 URL」。CosyVoice 本身的接入见文末第 6 节。
> ⚠️ 本仓库是 public，**任何 AccessKey / Secret 都不要写进代码或文档**，一律走 `.env`。

---

## 0. 先确认这笔账值不值

声音复刻只在**新建一个声线**时用一次，每个声线一个 10-20 秒的参考音频（几百 KB）。

| 项目 | 单价 | 本项目实际用量 | 月成本 |
| --- | --- | --- | --- |
| OSS 标准存储 | ≈0.12 元/GB/月 | < 10 MB | ≈0 元 |
| 外网下行流量 | ≈0.50 元/GB | 每个声线下载 1 次，< 1 MB | ≈0 元 |
| 请求次数 | ≈0.01 元/万次 | 几十次 | ≈0 元 |

结论：**OSS 这一层本身几乎不花钱**，成本全在 CosyVoice 合成侧（2 元/万字符，对比 MiniMax 便宜很多）。
真正的代价是一次性的开通+配置工作量（下面 1-4 节，约 20-30 分钟）。

---

## 1. 开通 OSS 并建 bucket

1. 登录阿里云控制台 → 搜索「对象存储 OSS」→ 开通服务（按量付费，不用买资源包）。
2. 创建 Bucket：
   - **地域**：选和百炼服务同区域的，优先 `华东1（杭州）`——同区域走内网，最快也最不容易被网络策略挡。
   - **Bucket 名称**：全局唯一，例如 `dove-podcast-voice-ref`。
   - **读写权限**：选 **私有**。不要选公共读——参考音频是别人的声音，没必要挂公网；下面用签名 URL 解决可访问性。
   - 版本控制 / 加密 / 冗余：全部保持默认。
3. 记下这三个值，后面要写进 `.env`：
   - Bucket 名（`dove-podcast-voice-ref`）
   - 地域 ID（`cn-hangzhou`）
   - Endpoint（`oss-cn-hangzhou.aliyuncs.com`）

---

## 2. 建一个只能碰这个 bucket 的 RAM 用户

**不要用主账号 AccessKey。** 主账号 key 泄露=整个云账号沦陷。

1. 控制台 → 访问控制 RAM → 用户 → 创建用户
   - 登录名：`podcast-oss-relay`
   - 访问方式：勾选 **使用永久 AccessKey 访问**（不需要控制台登录）
2. 创建完成页面会显示 **AccessKey ID** 和 **AccessKey Secret**，
   **Secret 只显示这一次**，当场复制走。
3. 给这个用户授权，权限收到最小：RAM → 权限策略 → 创建权限策略 → 脚本编辑，粘贴下面内容
   （把 `dove-podcast-voice-ref` 换成你的 bucket 名），然后把这条策略授权给 `podcast-oss-relay`。

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["oss:PutObject", "oss:GetObject", "oss:DeleteObject"],
      "Resource": ["acs:oss:*:*:dove-podcast-voice-ref/voice-ref/*"]
    }
  ]
}
```

这条策略的意思：这把 key 只能在这个 bucket 的 `voice-ref/` 目录下增删读，别的什么都干不了。

---

## 3. 写进 `.env`（不提交 git）

```bash
# 阿里云 OSS（音频中转，仅用于 CosyVoice 声音复刻）
ALIYUN_OSS_ACCESS_KEY_ID=
ALIYUN_OSS_ACCESS_KEY_SECRET=
ALIYUN_OSS_BUCKET=dove-podcast-voice-ref
ALIYUN_OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com

# 阿里云百炼（CosyVoice）
DASHSCOPE_API_KEY=
```

同步在 `.env.example` 里加上同样的**空**键名，方便换设备时知道要补什么。

---

## 4. 上传并拿到签名 URL

```bash
pip install oss2
```

`oss_relay.py`（放在 `podcast_addon/` 下）：

```python
"""把本地参考音频传到 OSS，返回一个带签名、限时有效的 URL，供 CosyVoice 声音复刻下载。
bucket 是私有的，所以必须用签名 URL；签名 URL 过期后链接自动失效，不会长期裸露在公网。"""
import os
import sys
from pathlib import Path

import oss2
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")


def upload_and_sign(local_path: Path, expire_seconds: int = 3600) -> str:
    auth = oss2.Auth(os.environ["ALIYUN_OSS_ACCESS_KEY_ID"],
                     os.environ["ALIYUN_OSS_ACCESS_KEY_SECRET"])
    endpoint = os.environ["ALIYUN_OSS_ENDPOINT"]
    bucket = oss2.Bucket(auth, f"https://{endpoint}", os.environ["ALIYUN_OSS_BUCKET"])

    key = f"voice-ref/{local_path.name}"
    bucket.put_object_from_file(key, str(local_path))
    # slash_safe=True：不要把 URL 里的 / 转义掉，否则百炼侧取不到文件
    return bucket.sign_url("GET", key, expire_seconds, slash_safe=True)


if __name__ == "__main__":
    url = upload_and_sign(Path(sys.argv[1]))
    print(url)
```

用法：

```bash
python oss_relay.py work/voice_ref/lex_fridman_20s.wav
```

**自检（必做，跳过这步会把 OSS 的问题误判成 CosyVoice 的问题）**：

```bash
curl -sI "<上一步打印出来的URL>" | head -3
```

期望看到 `HTTP/1.1 200 OK` 和 `Content-Type: audio/...`。
如果是 `403`，多半是 RAM 策略的 `Resource` 路径和实际 object key 对不上。

---

## 5. 参考音频本身的要求

复刻质量几乎全看这 10-20 秒喂得好不好：

- **格式**：wav 或 mp3；采样率 16kHz 及以上，单声道。
- **时长**：10-20 秒。太短音色不稳，太长没有额外收益。
- **内容**：单人连续说话，**不能有第二个人的声音、背景音乐、掌声、笑声**。
  播客的开场白通常带音乐，要往后找一段纯人声。
- **准备命令**（从已下载的原视频音频里截一段并转成 16k 单声道 wav）：

```bash
ffmpeg -y -i youtube_transcripts/_audio/<video_id>.mp3 -ss 00:03:12 -t 18 -ac 1 -ar 16000 work/voice_ref/<speaker>.wav
```

---

## 6. 接上 CosyVoice

```bash
pip install dashscope
```

```python
import os
from pathlib import Path

import dashscope
from dashscope.audio.tts_v2 import VoiceEnrollmentService, SpeechSynthesizer

from oss_relay import upload_and_sign

dashscope.api_key = os.environ["DASHSCOPE_API_KEY"]

# ① 复刻声线（每个说话人只做一次，voice_id 要登记进 voice_ids.md）
url = upload_and_sign(Path("work/voice_ref/lex.wav"))
service = VoiceEnrollmentService()
voice_id = service.create_voice(target_model="cosyvoice-v2", prefix="dove", url=url)
print("voice_id:", voice_id)

# ② 合成
synth = SpeechSynthesizer(model="cosyvoice-v2", voice=voice_id)
Path("out.mp3").write_bytes(synth.call("这是一段测试。"))
```

> ⚠️ 上面 `create_voice` 的参数名（`target_model` / `prefix` / `url`）是按百炼 Python SDK 的
> 常见形态写的，**首次联调时以官方文档当前版本为准**。真正需要验证的是前面第 4 节的 URL 能不能被下载——
> 这是 2026-09-02 卡住的地方，也是这份指南存在的唯一理由。

---

## 7. 联调 checklist

```
[ ] bucket 建好，权限=私有，地域=cn-hangzhou
[ ] RAM 用户建好，策略只覆盖 <bucket>/voice-ref/*
[ ] .env 四个 OSS 变量 + DASHSCOPE_API_KEY 都填了，.env.example 同步加了空键
[ ] pip install oss2 dashscope
[ ] oss_relay.py 跑通，curl -I 返回 200
[ ] create_voice 返回 voice_id（不再是 download audio failed）
[ ] 拿同一段文本分别用 MiniMax 和 CosyVoice 合成，A/B 试听后再决定是否切换
[ ] 切换决定写进 ../决策日志.md（结论 + why + 日期）
[ ] 新的 voice_id 登记进 voice_ids.md
```

**在 A/B 试听通过之前，不要把 CosyVoice 混进正在处理的集数**——2026-09-02 的结论是
「跑通前所有集数仍用 MiniMax，不要中途混用未验证方案」。
