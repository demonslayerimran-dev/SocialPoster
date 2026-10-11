"""
TikTok Content Posting API (فيديو فقط هنا).
ملاحظة: حتى توافق TikTok على التطبيق ديالك (audit)، المنشورات كتبقى خاصة (SELF_ONLY).
"""
import os
import requests

LABEL = "TikTok"
REQUIRED = ["TIKTOK_ACCESS_TOKEN"]
MEDIA = ["video"]


def post(file_path, media_type, caption, public_url=None):
    token = os.getenv("TIKTOK_ACCESS_TOKEN")
    size = os.path.getsize(file_path)
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}
    init = requests.post(
        "https://open.tiktokapis.com/v2/post/publish/video/init/",
        headers=headers,
        json={
            "post_info": {"title": caption[:2200],
                          "privacy_level": os.getenv("TIKTOK_PRIVACY", "SELF_ONLY")},
            "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                            "chunk_size": size, "total_chunk_count": 1},
        },
        timeout=60,
    ).json()
    if init.get("error", {}).get("code") not in (None, "ok"):
        raise RuntimeError(init["error"].get("message"))

    upload_url = init["data"]["upload_url"]
    with open(file_path, "rb") as f:
        r = requests.put(upload_url, data=f, timeout=600, headers={
            "Content-Type": "video/mp4",
            "Content-Range": f"bytes 0-{size - 1}/{size}",
        })
    if r.status_code >= 300:
        raise RuntimeError(r.text)
    return f"publish_id={init['data']['publish_id']}"
