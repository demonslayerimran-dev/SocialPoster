"""
كل منصة عندها ملف بوحدها فهاد الدوسي.
كل ملف فيه:
  LABEL     -> السمية اللي كتبان فالواجهة
  REQUIRED  -> المفاتيح اللي خاصهم يكونو فـ .env
  MEDIA     -> نوع الملفات اللي كتقبل: "image" و/أو "video"
  post(file_path, media_type, caption, public_url) -> كترجع رابط أو ID ديال المنشور
"""
import os

import config

from . import telegram, discord, facebook, instagram, youtube, tiktok, x, linkedin, pinterest

ALL = {
    "telegram": telegram,
    "discord": discord,
    "facebook": facebook,
    "instagram": instagram,
    "youtube": youtube,
    "tiktok": tiktok,
    "x": x,
    "linkedin": linkedin,
    "pinterest": pinterest,
}


def missing_keys(module):
    """كترجع لائحة المفاتيح اللي ناقصين فـ .env"""
    return [k for k in module.REQUIRED if not os.getenv(k)]


def status():
    """حالة كل منصة: واش مربوطة ولا لا"""
    out = {}
    for key, mod in ALL.items():
        miss = missing_keys(mod)
        if key == "youtube" and not os.path.exists(config.YOUTUBE_TOKEN):
            miss = miss + ["ربط الحساب من الإعدادات"]
        if key == "instagram" and not (os.getenv("IG_PAGE_TOKEN") or os.getenv("FB_PAGE_ACCESS_TOKEN")):
            miss = miss + ["ربط الحساب من الإعدادات"]
        if key == "tiktok" and not os.path.exists(config.TIKTOK_TOKEN):
            miss = miss + ["ربط الحساب من الإعدادات"]
        out[key] = {"label": mod.LABEL, "media": mod.MEDIA, "ready": not miss, "missing": miss}
    return out
