import os
import requests

LABEL = "Discord"
REQUIRED = ["DISCORD_WEBHOOK_URL"]
MEDIA = ["image", "video"]


def post(file_path, media_type, caption, public_url=None):
    url = os.getenv("DISCORD_WEBHOOK_URL")
    with open(file_path, "rb") as f:
        r = requests.post(
            url + "?wait=true",
            data={"content": caption[:2000]},
            files={"file": (os.path.basename(file_path), f)},
            timeout=300,
        )
    if r.status_code >= 300:
        raise RuntimeError(r.text)
    return f"message_id={r.json().get('id')}"
