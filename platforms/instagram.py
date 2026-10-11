"""
Instagram ما كيقبلش الملف مباشرة: خاص الملف يكون فرابط عمومي (public URL)
باش Instagram يجي ياخدو. شوف README (PUBLIC_BASE_URL).
"""
import os
import time
import requests

LABEL = "Instagram"
REQUIRED = ["IG_USER_ID", "FB_PAGE_ACCESS_TOKEN", "PUBLIC_BASE_URL"]
MEDIA = ["image", "video"]
API = "https://graph.facebook.com/v21.0"


def _check(r):
    j = r.json()
    if "error" in j:
        raise RuntimeError(j["error"].get("message"))
    return j


def post(file_path, media_type, caption, public_url=None):
    ig = os.getenv("IG_USER_ID")
    token = os.getenv("FB_PAGE_ACCESS_TOKEN")
    if not public_url:
        raise RuntimeError("Instagram محتاج PUBLIC_BASE_URL")

    data = {"caption": caption[:2200], "access_token": token}
    if media_type == "image":
        data["image_url"] = public_url
    else:
        data["media_type"] = "REELS"
        data["video_url"] = public_url
    container = _check(requests.post(f"{API}/{ig}/media", data=data, timeout=120))["id"]

    # نتسناو حتى يكمل Instagram المعالجة (خصوصا الفيديو)
    for _ in range(60):
        s = _check(requests.get(f"{API}/{container}",
                                params={"fields": "status_code", "access_token": token}, timeout=30))
        if s.get("status_code") in (None, "FINISHED"):
            break
        if s.get("status_code") == "ERROR":
            raise RuntimeError("Instagram رفض الملف (شوف الصيغة والحجم)")
        time.sleep(5)

    pub = _check(requests.post(f"{API}/{ig}/media_publish",
                               data={"creation_id": container, "access_token": token}, timeout=60))
    return f"id={pub['id']}"
