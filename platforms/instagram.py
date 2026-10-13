"""
Instagram (حساب Professional مربوط بصفحة Facebook).
- الفيديو (Reels): كيترفع مباشرة لـ Instagram (resumable upload) — بلا ngrok.
- الصورة: Instagram كيطلب رابط، فكنرفعوها أولا لصفحة Facebook بلا نشر (published=false)
  وكناخدو الرابط ديالها من Facebook.
"""
import os
import time

import requests

LABEL = "Instagram"
REQUIRED = ["IG_USER_ID"]
MEDIA = ["image", "video"]
VER = "v21.0"
API = f"https://graph.facebook.com/{VER}"


def _check(r):
    j = r.json()
    if "error" in j:
        raise RuntimeError(j["error"].get("error_user_msg") or j["error"].get("message"))
    return j


def creds():
    """Instagram عندو الصفحة والتوكن ديالو (مستقلين على Facebook)؛ النسخ القديمة كترجع للديال Facebook"""
    return (os.getenv("IG_PAGE_ID") or os.getenv("FB_PAGE_ID"),
            os.getenv("IG_PAGE_TOKEN") or os.getenv("FB_PAGE_ACCESS_TOKEN"))


def _image_url(file_path, token):
    """كنرفعو الصورة للصفحة المربوطة بـ Instagram بلا ما تبان، وكناخدو الرابط ديالها"""
    page = creds()[0]
    with open(file_path, "rb") as f:
        pid = _check(requests.post(f"{API}/{page}/photos", timeout=300,
                                   data={"published": "false", "access_token": token},
                                   files={"source": f}))["id"]
    imgs = _check(requests.get(f"{API}/{pid}", timeout=30,
                               params={"fields": "images", "access_token": token}))["images"]
    return max(imgs, key=lambda i: i["width"])["source"]


def post(file_path, media_type, caption, public_url=None):
    ig = os.getenv("IG_USER_ID")
    token = creds()[1]
    caption = caption[:2200]

    if media_type == "image":
        container = _check(requests.post(f"{API}/{ig}/media", timeout=120, data={
            "image_url": _image_url(file_path, token), "caption": caption, "access_token": token}))["id"]
    else:
        container = _check(requests.post(f"{API}/{ig}/media", timeout=120, data={
            "media_type": "REELS", "upload_type": "resumable", "caption": caption,
            "share_to_feed": "true", "access_token": token}))["id"]
        size = os.path.getsize(file_path)
        with open(file_path, "rb") as f:
            r = requests.post(f"https://rupload.facebook.com/ig-api-upload/{VER}/{container}",
                              data=f, timeout=1800, headers={
                                  "Authorization": f"OAuth {token}",
                                  "offset": "0", "file_size": str(size)})
        if r.status_code >= 300:
            raise RuntimeError(f"فشل رفع الفيديو لـ Instagram: {r.text[:200]}")

    # نتسناو Instagram يكمل المعالجة (الفيديو كياخد شوية)
    for _ in range(120):
        s = _check(requests.get(f"{API}/{container}", timeout=30,
                                params={"fields": "status_code,status", "access_token": token}))
        code = s.get("status_code")
        if code in (None, "FINISHED"):
            break
        if code in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Instagram رفض الملف: {s.get('status') or code}")
        time.sleep(5)
    else:
        raise RuntimeError("Instagram طول بزاف فالمعالجة، جرب «عاود» من بعد")

    pub = _check(requests.post(f"{API}/{ig}/media_publish", timeout=60,
                               data={"creation_id": container, "access_token": token}))
    try:
        link = _check(requests.get(f"{API}/{pub['id']}", timeout=30,
                                   params={"fields": "permalink", "access_token": token})).get("permalink")
    except Exception:
        link = None
    return link or f"id={pub['id']}"
