"""
Clone a MiniMax voice from a local audio sample.
"""
import argparse
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


HERE = Path(__file__).parent
load_dotenv(HERE / ".env")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("--voice-id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--text", default="这是一段用于确认声线克隆效果的中文试听音频。")
    args = ap.parse_args()

    api_key = os.getenv("MINIMAX_API_KEY", "")
    if not api_key or api_key == "换成你重新生成的新key":
        raise SystemExit("MINIMAX_API_KEY is not set")

    headers = {"Authorization": f"Bearer {api_key}"}
    audio_path = Path(args.audio)
    with audio_path.open("rb") as f:
        upload = requests.post(
            "https://api.minimax.io/v1/files/upload",
            headers=headers,
            files={"file": (audio_path.name, f, "audio/mpeg")},
            data={"purpose": "voice_clone"},
            timeout=120,
        )
    upload.raise_for_status()
    upload_data = upload.json()
    file_id = upload_data.get("file", {}).get("file_id") or upload_data.get("file_id")
    if not file_id:
        raise RuntimeError(f"No file_id in upload response: {upload_data}")

    clone = requests.post(
        "https://api.minimax.io/v1/voice_clone",
        headers={**headers, "Content-Type": "application/json"},
        json={
            "file_id": file_id,
            "voice_id": args.voice_id,
            "text": args.text,
            "model": "speech-02-hd",
            "need_noise_reduction": True,
            "accuracy": 0.8,
        },
        timeout=120,
    )
    clone.raise_for_status()
    clone_data = clone.json()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {"voice_id": args.voice_id, "file_id": file_id, "upload": upload_data, "clone": clone_data},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"cloned: {args.voice_id}")


if __name__ == "__main__":
    main()
