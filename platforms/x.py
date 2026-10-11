"""
X (Twitter): خاص اشتراك فـ X API كيسمح بالنشر.
"""
import os

LABEL = "X (Twitter)"
REQUIRED = ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"]
MEDIA = ["image", "video"]


def post(file_path, media_type, caption, public_url=None):
    import tweepy

    k = [os.getenv(n) for n in REQUIRED]
    api_v1 = tweepy.API(tweepy.OAuth1UserHandler(*k))
    media = api_v1.media_upload(
        filename=file_path,
        chunked=(media_type == "video"),
        media_category="tweet_video" if media_type == "video" else "tweet_image",
    )
    client = tweepy.Client(consumer_key=k[0], consumer_secret=k[1],
                           access_token=k[2], access_token_secret=k[3])
    resp = client.create_tweet(text=caption[:280], media_ids=[media.media_id])
    return f"https://x.com/i/status/{resp.data['id']}"
