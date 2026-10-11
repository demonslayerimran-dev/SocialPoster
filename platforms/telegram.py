import os
import requests

LABEL = "Telegram"
REQUIRED = ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"]
MEDIA = ["image", "video"]


def post(file_path, media_type, caption, public_url=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    method, field = ("sendPhoto", "photo") if media_type == "image" else ("sendVideo", "video")
    with open(file_path, "rb") as f:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/{method}",
            data={"chat_id": chat_id, "caption": caption[:1024]},
            files={field: f},
            timeout=300,
        )
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(data.get("description", r.text))
    return f"message_id={data['result']['message_id']}"
