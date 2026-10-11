"""
YouTube: كيقبل غير الفيديو.
كيتربط من صفحة الإعدادات (زر "ربط YouTube")
"""
import os

import config

LABEL = "YouTube"
REQUIRED = []  # كيعتمد على youtube_token.json
MEDIA = ["video"]


def post(file_path, media_type, caption, public_url=None):
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    creds = Credentials.from_authorized_user_file(config.YOUTUBE_TOKEN)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        with open(config.YOUTUBE_TOKEN, "w") as f:
            f.write(creds.to_json())

    yt = build("youtube", "v3", credentials=creds)
    title = (caption.splitlines()[0] if caption else os.path.basename(file_path))[:100]
    body = {
        "snippet": {"title": title, "description": caption[:5000]},
        "status": {"privacyStatus": os.getenv("YOUTUBE_PRIVACY", "public")},
    }
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(file_path, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    return f"https://youtu.be/{resp['id']}"
