"""
LinkedIn: هاد النسخة كتنشر الصور + النص.
LINKEDIN_AUTHOR مثلا: urn:li:person:XXXX  أو  urn:li:organization:XXXX
"""
import os
import requests

LABEL = "LinkedIn"
REQUIRED = ["LINKEDIN_ACCESS_TOKEN", "LINKEDIN_AUTHOR"]
MEDIA = ["image"]


def post(file_path, media_type, caption, public_url=None):
    token = os.getenv("LINKEDIN_ACCESS_TOKEN")
    author = os.getenv("LINKEDIN_AUTHOR")
    h = {"Authorization": f"Bearer {token}", "LinkedIn-Version": "202409",
         "X-Restli-Protocol-Version": "2.0.0", "Content-Type": "application/json"}

    init = requests.post("https://api.linkedin.com/rest/images?action=initializeUpload",
                         headers=h, json={"initializeUploadRequest": {"owner": author}}, timeout=60)
    if init.status_code >= 300:
        raise RuntimeError(init.text)
    val = init.json()["value"]
    with open(file_path, "rb") as f:
        up = requests.put(val["uploadUrl"], data=f, headers={"Authorization": f"Bearer {token}"}, timeout=300)
    if up.status_code >= 300:
        raise RuntimeError(up.text)

    r = requests.post("https://api.linkedin.com/rest/posts", headers=h, timeout=60, json={
        "author": author,
        "commentary": caption[:3000],
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED"},
        "content": {"media": {"id": val["image"]}},
        "lifecycleState": "PUBLISHED",
    })
    if r.status_code >= 300:
        raise RuntimeError(r.text)
    return r.headers.get("x-restli-id", "ok")
