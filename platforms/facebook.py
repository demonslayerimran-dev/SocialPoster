import os
import requests

LABEL = "Facebook (Page)"
REQUIRED = ["FB_PAGE_ID", "FB_PAGE_ACCESS_TOKEN"]
MEDIA = ["image", "video"]
API = "v21.0"


def post(file_path, media_type, caption, public_url=None):
    page = os.getenv("FB_PAGE_ID")
    token = os.getenv("FB_PAGE_ACCESS_TOKEN")
    if media_type == "image":
        url = f"https://graph.facebook.com/{API}/{page}/photos"
        data = {"caption": caption, "access_token": token}
    else:
        url = f"https://graph-video.facebook.com/{API}/{page}/videos"
        data = {"description": caption, "access_token": token}
    with open(file_path, "rb") as f:
        r = requests.post(url, data=data, files={"source": f}, timeout=600)
    j = r.json()
    if "error" in j:
        raise RuntimeError(j["error"].get("message"))
    return f"id={j.get('post_id') or j.get('id')}"
