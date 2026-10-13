"""
الـ Tags: كتكتبهم مرة وحدة، والبرنامج كيحطهم فكل منصة بالطريقة ديالها:
  - YouTube: كيوليو Tags حقيقيين (حقل tags) + #hashtags فالوصف
  - باقي المنصات: كيتزادو كـ #hashtags فآخر النص
"""
import re

# الحد ديال النص فكل منصة (باش الهاشتاغات ما يتقطعوش)
LIMITS = {"x": 280, "telegram": 1024, "discord": 2000, "pinterest": 500,
          "instagram": 2200, "tiktok": 2200, "linkedin": 3000, "youtube": 5000}
MAX_HASHTAGS = {"instagram": 30, "youtube": 15, "x": 5}


def parse(raw):
    """'trading, #forex تداول' ← ['trading', 'forex', 'تداول']"""
    out = []
    for t in re.split(r"[,\n،;]+|\s+", raw or ""):
        t = re.sub(r"[^\w]", "", t.strip().lstrip("#"), flags=re.UNICODE)
        if t and t.lower() not in (x.lower() for x in out):
            out.append(t)
    return out


def caption_for(platform, caption, tags):
    """النص النهائي ديال منصة: النص + الهاشتاغات اللي مازال ما كاينينش فيه"""
    caption = (caption or "").strip()
    present = {m.lower() for m in re.findall(r"#(\w+)", caption, flags=re.UNICODE)}
    extra = [t for t in tags if t.lower() not in present][:MAX_HASHTAGS.get(platform, 30)]
    tail = " ".join("#" + t for t in extra)
    limit = LIMITS.get(platform)
    if limit and tail:
        # نقصو من النص (ماشي من الهاشتاغات) إلا كان طويل
        room = limit - len(tail) - 2
        if room < 20:  # بزاف ديال الهاشتاغات: نحيدو حتى يدخلو
            while extra and len(" ".join("#" + t for t in extra)) > limit // 2:
                extra.pop()
            tail = " ".join("#" + t for t in extra)
            room = limit - len(tail) - 2
        if len(caption) > room:
            caption = caption[:max(room - 1, 0)].rstrip() + "…"
    return f"{caption}\n\n{tail}".strip() if tail else caption


def youtube_tags(tags):
    """YouTube: مجموع الـ tags خاصو يكون أقل من 500 حرف"""
    out, total = [], 0
    for t in tags:
        if total + len(t) + 1 > 480:
            break
        out.append(t)
        total += len(t) + 1
    return out
