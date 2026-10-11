"""
الإعدادات ديال البرنامج.
كلشي كيتحفظ فـ:  %APPDATA%\\SocialPoster   (فـ Windows)
باش ملي تبدل البرنامج ولا تحدثو، ما تضيعش المفاتيح والسجل.
"""
import json
import os
import sys

APP_NAME = "SocialPoster"

if sys.platform == "win32":
    DATA_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP_NAME)
else:
    DATA_DIR = os.path.join(os.path.expanduser("~"), "." + APP_NAME.lower())

UPLOADS = os.path.join(DATA_DIR, "uploads")
DB = os.path.join(DATA_DIR, "posts.db")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")
YOUTUBE_TOKEN = os.path.join(DATA_DIR, "youtube_token.json")
YOUTUBE_SECRET = os.path.join(DATA_DIR, "client_secret.json")

os.makedirs(UPLOADS, exist_ok=True)


def resource_path(rel):
    """المسار ديال الملفات (templates...) سواء فالكود ولا داخل الـ exe"""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


# كل الخانات اللي كتبان فصفحة الإعدادات
# (المفتاح, السمية, سري؟, مثال/شرح)
FIELDS = {
    "general": {
        "title": "عام",
        "help": "",
        "fields": [
            ("DRY_RUN", "وضع التجربة (ما ينشر والو بصح)", "bool", ""),
            ("START_WITH_WINDOWS", "شغل البرنامج مع Windows (باش النشر المبرمج ما يفوتكش)", "bool", ""),
        ],
    },
    "telegram": {
        "title": "Telegram",
        "help": "كتب لـ @BotFather ← /newbot ← خود التوكن. زيد البوت كـ Admin فالقناة.",
        "fields": [
            ("TELEGRAM_BOT_TOKEN", "Bot Token", "secret", "123456:ABC-DEF..."),
            ("TELEGRAM_CHAT_ID", "Chat ID ولا @smiyat_l9ana", "text", "@my_channel"),
        ],
    },
    "discord": {
        "title": "Discord",
        "help": "Server Settings ← Integrations ← Webhooks ← New Webhook ← Copy Webhook URL",
        "fields": [("DISCORD_WEBHOOK_URL", "Webhook URL", "secret", "https://discord.com/api/webhooks/...")],
    },
    "facebook": {
        "title": "Facebook Page + Instagram",
        "help": "developers.facebook.com ← App ← Graph API Explorer ← Page Access Token "
                "(pages_manage_posts, instagram_content_publish). Instagram خاصو حساب Business/Creator مربوط بالصفحة.",
        "fields": [
            ("FB_PAGE_ID", "Page ID", "text", ""),
            ("FB_PAGE_ACCESS_TOKEN", "Page Access Token", "secret", ""),
            ("IG_USER_ID", "Instagram User ID", "text", ""),
            ("PUBLIC_BASE_URL", "رابط عمومي (لـ Instagram فقط، مثلا من ngrok)", "text", "https://xxxx.ngrok-free.app"),
        ],
    },
    "youtube": {
        "title": "YouTube",
        "help": "console.cloud.google.com ← فعل YouTube Data API v3 ← OAuth client ID (Desktop app) ← نزل client_secret.json",
        "fields": [("YOUTUBE_PRIVACY", "الخصوصية: public / unlisted / private", "text", "public")],
    },
    "tiktok": {
        "title": "TikTok",
        "help": "developers.tiktok.com ← Content Posting API. حتى توافق TikTok على التطبيق، الفيديوهات كيبقاو خاصين.",
        "fields": [
            ("TIKTOK_ACCESS_TOKEN", "Access Token", "secret", ""),
            ("TIKTOK_PRIVACY", "SELF_ONLY ولا PUBLIC_TO_EVERYONE", "text", "SELF_ONLY"),
        ],
    },
    "x": {
        "title": "X (Twitter)",
        "help": "developer.x.com ← App بصلاحية Read and Write ← 4 مفاتيح OAuth 1.0a. (النشر بالخلاص)",
        "fields": [
            ("X_API_KEY", "API Key", "secret", ""),
            ("X_API_SECRET", "API Secret", "secret", ""),
            ("X_ACCESS_TOKEN", "Access Token", "secret", ""),
            ("X_ACCESS_SECRET", "Access Secret", "secret", ""),
        ],
    },
    "linkedin": {
        "title": "LinkedIn",
        "help": "developer.linkedin.com ← Share on LinkedIn ← توكن بصلاحية w_member_social",
        "fields": [
            ("LINKEDIN_ACCESS_TOKEN", "Access Token", "secret", ""),
            ("LINKEDIN_AUTHOR", "Author URN", "text", "urn:li:person:XXXX"),
        ],
    },
    "pinterest": {
        "title": "Pinterest",
        "help": "developers.pinterest.com ← App ← توكن بصلاحية pins:write",
        "fields": [
            ("PINTEREST_ACCESS_TOKEN", "Access Token", "secret", ""),
            ("PINTEREST_BOARD_ID", "Board ID", "text", ""),
        ],
    },
}

DEFAULTS = {"DRY_RUN": "1", "START_WITH_WINDOWS": "0", "YOUTUBE_PRIVACY": "public", "TIKTOK_PRIVACY": "SELF_ONLY"}


def load():
    """كيقرا الإعدادات وكيحطهم فـ os.environ باش المنصات يلقاوهم"""
    data = dict(DEFAULTS)
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            data.update(json.load(f))
    for k, v in data.items():
        os.environ[k] = str(v)
    return data


def save(new):
    data = load()
    data.update({k: (v.strip() or DEFAULTS.get(k, "")) for k, v in new.items()})
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    for k, v in data.items():
        os.environ[k] = str(v)
    return data


def set_start_with_windows(enabled):
    """كيزيد/كيحيد البرنامج من التشغيل التلقائي مع Windows"""
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return
    import winreg
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                         r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
    try:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{sys.executable}" --minimized')
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
    finally:
        winreg.CloseKey(key)
