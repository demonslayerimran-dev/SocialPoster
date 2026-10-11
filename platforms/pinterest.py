"""
Pinterest: هاد النسخة كتنشر الصور فـ board معين.
"""
import base64
import mimetypes
import os
import requests

LABEL = "Pinterest"
REQUIRED = ["PINTEREST_ACCESS_TOKEN", "PINTEREST_BOARD_ID"]
MEDIA = ["image"]


def post(file_path, media_type, caption, public_url=None):
    with open(file_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    ctype = mimetypes.guess_type(file_path)[0] or "image/jpeg"
    title = (caption.splitlines()[0] if caption else "")[:100]
    r = requests.post(
        "https://api.pinterest.com/v5/pins",
        headers={"Authorization": f"Bearer {os.getenv('PINTEREST_ACCESS_TOKEN')}"},
        json={
            "board_id": os.getenv("PINTEREST_BOARD_ID"),
            "title": title,
            "description": caption[:500],
            "media_source": {"source_type": "image_base64", "content_type": ctype, "data": b64},
        },
        timeout=120,
    )
    if r.status_code >= 300:
        raise RuntimeError(r.text)
    return f"https://www.pinterest.com/pin/{r.json()['id']}"
