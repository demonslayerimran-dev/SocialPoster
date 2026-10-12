"""
TikTok Content Posting API (فيديو فقط).
الربط كيتدار من الإعدادات (زر «ربط TikTok»)، والتوكن كيتجدد بوحدو.
ملاحظة: حتى توافق TikTok على التطبيق ديالك (audit)، المنشورات كتبقى خاصة (SELF_ONLY).
"""
import json
import os
import time

import requests

import config

LABEL = "TikTok"
REQUIRED = ["TIKTOK_CLIENT_KEY", "TIKTOK_CLIENT_SECRET"]
MEDIA = ["video"]

API = "https://open.tiktokapis.com/v2"
SCOPES = "user.info.basic,video.publish"


# ---------------- التوكن ----------------
def save_token(data):
    data["expires_at"] = time.time() + int(data.get("expires_in", 86400)) - 300
    with open(config.TIKTOK_TOKEN, "w") as f:
        json.dump(data, f)


def exchange_code(code, redirect_uri):
    r = requests.post(f"{API}/oauth/token/", timeout=30, data={
        "client_key": os.getenv("TIKTOK_CLIENT_KEY"),
        "client_secret": os.getenv("TIKTOK_CLIENT_SECRET"),
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    j = r.json()
    if "access_token" not in j:
        raise RuntimeError(j.get("error_description") or j.get("error") or r.text)
    save_token(j)


def access_token():
    if not os.path.exists(config.TIKTOK_TOKEN):
        raise RuntimeError("TikTok ماشي مربوط — سير للإعدادات وضغط «ربط TikTok»")
    with open(config.TIKTOK_TOKEN) as f:
        tok = json.load(f)
    if time.time() < tok.get("expires_at", 0):
        return tok["access_token"]
    # التوكن تسالا: نجددوه بالـ refresh_token
    r = requests.post(f"{API}/oauth/token/", timeout=30, data={
        "client_key": os.getenv("TIKTOK_CLIENT_KEY"),
        "client_secret": os.getenv("TIKTOK_CLIENT_SECRET"),
        "grant_type": "refresh_token",
        "refresh_token": tok["refresh_token"],
    }, headers={"Content-Type": "application/x-www-form-urlencoded"})
    j = r.json()
    if "access_token" not in j:
        raise RuntimeError("تسالا الربط ديال TikTok، عاود «ربط TikTok» من الإعدادات")
    save_token(j)
    return j["access_token"]


def _check(r):
    j = r.json()
    err = j.get("error", {})
    if err.get("code") not in (None, "ok"):
        raise RuntimeError(f"{err.get('code')}: {err.get('message')}")
    return j.get("data", {})


# ---------------- النشر ----------------
def post(file_path, media_type, caption, public_url=None):
    token = access_token()
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=UTF-8"}

    # 1) TikTok كتفرض نسولو على الإعدادات المسموحة للحساب
    info = _check(requests.post(f"{API}/post/publish/creator_info/query/", headers=h, timeout=30))
    allowed = info.get("privacy_level_options") or ["SELF_ONLY"]
    privacy = os.getenv("TIKTOK_PRIVACY", "SELF_ONLY")
    if privacy not in allowed:
        privacy = "SELF_ONLY" if "SELF_ONLY" in allowed else allowed[0]

    # 2) حساب الأجزاء (chunks): أقل من 64MB = جزء واحد
    size = os.path.getsize(file_path)
    if size <= 64 * 1024 * 1024:
        chunk, count = size, 1
    else:
        chunk = 10 * 1024 * 1024
        count = size // chunk  # الجزء الأخير كياخد الباقي

    init = _check(requests.post(f"{API}/post/publish/video/init/", headers=h, timeout=60, json={
        "post_info": {"title": caption[:2200], "privacy_level": privacy},
        "source_info": {"source": "FILE_UPLOAD", "video_size": size,
                        "chunk_size": chunk, "total_chunk_count": count},
    }))

    # 3) رفع الفيديو
    with open(file_path, "rb") as f:
        for i in range(count):
            start = i * chunk
            end = size - 1 if i == count - 1 else start + chunk - 1
            f.seek(start)
            data = f.read(end - start + 1)
            r = requests.put(init["upload_url"], data=data, timeout=600, headers={
                "Content-Type": "video/mp4",
                "Content-Length": str(len(data)),
                "Content-Range": f"bytes {start}-{end}/{size}",
            })
            if r.status_code >= 300:
                raise RuntimeError(f"فشل رفع الجزء {i + 1}: {r.text[:200]}")

    # 4) نتسناو TikTok يكمل المعالجة
    pid = init["publish_id"]
    for _ in range(36):
        time.sleep(5)
        st = _check(requests.post(f"{API}/post/publish/status/fetch/", headers=h, timeout=30,
                                  json={"publish_id": pid}))
        s = st.get("status")
        if s == "PUBLISH_COMPLETE":
            note = " (خاص — حتى توافق TikTok على التطبيق)" if privacy == "SELF_ONLY" else ""
            return f"تنشر{note}"
        if s == "FAILED":
            raise RuntimeError(f"TikTok رفض الفيديو: {st.get('fail_reason')}")
    return f"تطلع، TikTok مازال كيعالجو (publish_id={pid})"
