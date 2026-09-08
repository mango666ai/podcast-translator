"""
用 CosyVoice 声音复刻克隆一个声线（免费，不像火山引擎那样收 138 元/音色槽位费）。

跟 clone_minimax_voice.py 的关键差异，接线时别踩：
  1. **voice_id 不能自己指定**，由服务端返回（形如 `cosyvoice-v2-<prefix>-<hash>`），
     所以这里的参数是 `--prefix` 而不是 `--voice-id`；真实 id 从输出 json 里读。
  2. 复刻接口**不接受直接上传音频/base64**，只认一个能下载到的 URL，
     而且这个 URL **必须国内可访问**（实测 raw.githubusercontent.com 会报
     `download audio failed`）。所以先把样本传到阿里云 OSS，再用**临时签名 URL**
     喂给它——bucket 保持私有，签名 1 小时后自动失效，不用把桶设成公共读。
  3. 样本要求 10~20 秒（最长 60 秒）、≤10MB，含至少 5 秒连续清晰人声。

用法：
    "$VENV_PY" clone_cosyvoice_voice.py <样本音频> --prefix lexfridman \
        --out youtube_dub/<集目录>/<video_id>_lex_cosyvoice.json
"""

import argparse
import json
import os
import uuid
from pathlib import Path

import oss2
import requests
from dotenv import load_dotenv

HERE = Path(__file__).parent
load_dotenv(HERE / ".env")

CLONE_URL = "https://dashscope.aliyuncs.com/api/v1/services/audio/tts/customization"
# 必须和 tts_cosyvoice.MODEL 保持一致，否则克隆出来的 voice_id 在合成时用不了
TARGET_MODEL = "cosyvoice-v3.5-plus"
SIGNED_URL_TTL = 3600


def upload_and_sign(local_path: Path) -> str:
    """传到 OSS 并返回 1 小时有效的签名 URL。"""
    ak = os.getenv("OSS_ACCESS_KEY_ID", "")
    sk = os.getenv("OSS_ACCESS_KEY_SECRET", "")
    bucket_name = os.getenv("OSS_BUCKET", "")
    endpoint = os.getenv("OSS_ENDPOINT", "")
    if not all([ak, sk, bucket_name, endpoint]):
        raise SystemExit("OSS_* 环境变量不完整（见 .env.example）")

    bucket = oss2.Bucket(oss2.Auth(ak, sk), f"https://{endpoint}", bucket_name)
    key = f"voice_samples/{uuid.uuid4().hex}_{local_path.name}"
    bucket.put_object_from_file(key, str(local_path))
    return bucket.sign_url("GET", key, SIGNED_URL_TTL, slash_safe=True)


def clone(audio_url: str, prefix: str) -> dict:
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise SystemExit("DASHSCOPE_API_KEY 未设置")

    resp = requests.post(
        CLONE_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": "voice-enrollment",
            "input": {
                "action": "create_voice",
                "target_model": TARGET_MODEL,
                "prefix": prefix,
                "url": audio_url,
            },
        },
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--prefix", required=True,
                    help="音色前缀（小写字母数字，服务端会在后面拼 hash 组成真实 voice_id）")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    signed = upload_and_sign(Path(args.audio))
    data = clone(signed, args.prefix)
    voice_id = data.get("output", {}).get("voice_id", "")
    if not voice_id:
        raise SystemExit(f"复刻失败，返回：{json.dumps(data, ensure_ascii=False)}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"voice_id": voice_id, "prefix": args.prefix, "clone": data},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"cloned: {voice_id}")


if __name__ == "__main__":
    main()
