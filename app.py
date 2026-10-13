"""
السيرفر الداخلي ديال البرنامج (الواجهة + النشر + الجدولة).
ما كتشغلوش بوحدو: desktop.py هو اللي كيشغلو داخل نافذة Windows.
"""
import os
import sqlite3
import threading
import uuid
from datetime import datetime

from flask import Flask, flash, redirect, render_template, request, send_from_directory, url_for

import config

config.load()
import platforms  # noqa: E402
import tags as tagslib  # noqa: E402

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".m4v"}

app = Flask(__name__, template_folder=config.resource_path("templates"))
app.secret_key = uuid.uuid4().hex
# باش الواجهة تقدر تبين النص النهائي (مع الهاشتاغات) ديال كل منصة
app.jinja_env.globals["caption_for"] = lambda platform, caption, tags: tagslib.caption_for(
    platform, caption, tagslib.parse(tags))
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2GB
lock = threading.Lock()
youtube_state = {"msg": ""}


@app.before_request
def only_media_from_outside():
    """إلا جا الطلب من برا (ngrok)، نسمحو غير بالملفات ديال Instagram — ماشي الإعدادات"""
    host = request.host.split(":")[0]
    external = host not in ("127.0.0.1", "localhost") or request.headers.get("X-Forwarded-For")
    if external and not request.path.startswith("/media/"):
        return "Forbidden", 403


def dry_run():
    return os.getenv("DRY_RUN", "1") == "1"


# ---------------- قاعدة البيانات ----------------
def db():
    con = sqlite3.connect(config.DB)
    con.row_factory = sqlite3.Row
    return con


def init_db():
    with db() as con:
        con.execute("""CREATE TABLE IF NOT EXISTS posts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file TEXT, media_type TEXT, caption TEXT,
            run_at TEXT, created_at TEXT, status TEXT)""")
        con.execute("""CREATE TABLE IF NOT EXISTS results(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER, platform TEXT, status TEXT, detail TEXT)""")
        # النسخ القديمة ما فيهاش العمود ديال tags
        cols = [r[1] for r in con.execute("PRAGMA table_info(posts)")]
        if "tags" not in cols:
            con.execute("ALTER TABLE posts ADD COLUMN tags TEXT DEFAULT ''")
        # إلا تسد البرنامج وسط النشر، نرجعو المنشور للانتظار
        con.execute("UPDATE posts SET status='scheduled' WHERE status='running'")


def pending_count():
    with db() as con:
        return con.execute("SELECT COUNT(*) FROM posts WHERE status='scheduled'").fetchone()[0]


# ---------------- النشر ----------------
def publish(post_id):
    with db() as con:
        p = con.execute("SELECT * FROM posts WHERE id=?", (post_id,)).fetchone()
        targets = con.execute("SELECT * FROM results WHERE post_id=? AND status='pending'",
                              (post_id,)).fetchall()
        con.execute("UPDATE posts SET status='running' WHERE id=?", (post_id,))

    path = os.path.join(config.UPLOADS, p["file"])
    base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
    public_url = f"{base_url}/media/{p['file']}" if base_url else None

    ok_count = 0
    for t in targets:
        mod = platforms.ALL[t["platform"]]
        try:
            if dry_run():
                detail = "وضع التجربة: ما تنشرش بصح"
            else:
                tag_list = tagslib.parse(p["tags"])
                text = tagslib.caption_for(t["platform"], p["caption"], tag_list)
                extra = {"tags": tagslib.youtube_tags(tag_list)} if t["platform"] == "youtube" else {}
                detail = mod.post(path, p["media_type"], text, public_url, **extra)
            status = "ok"
            ok_count += 1
        except Exception as e:  # كنسجلو الخطأ ونكملو مع المنصات الأخرى
            status, detail = "error", str(e)[:500]
        with db() as con:
            con.execute("UPDATE results SET status=?, detail=? WHERE id=?", (status, detail, t["id"]))

    final = "done" if ok_count == len(targets) else ("partial" if ok_count else "failed")
    with db() as con:
        con.execute("UPDATE posts SET status=? WHERE id=?", (final, post_id))


def check_due():
    """كتخدم كل 30 ثانية: كتنشر المنشورات اللي وصل الوقت ديالهم"""
    if not lock.acquire(blocking=False):
        return
    try:
        now = datetime.now().strftime("%Y-%m-%dT%H:%M")
        with db() as con:
            due = [r["id"] for r in con.execute(
                "SELECT id FROM posts WHERE status='scheduled' AND run_at<=?", (now,))]
        for pid in due:
            publish(pid)
    finally:
        lock.release()


def publish_now(pid):
    with lock:
        publish(pid)


# ---------------- صفحة النشر ----------------
@app.route("/")
def index():
    with db() as con:
        posts = con.execute("SELECT * FROM posts ORDER BY id DESC LIMIT 50").fetchall()
        results = {}
        for r in con.execute("SELECT * FROM results"):
            results.setdefault(r["post_id"], []).append(r)
    st = platforms.status()
    last_tags = next((p["tags"] for p in posts if p["tags"]), "")
    return render_template("index.html", status=st, posts=posts, results=results, last_tags=last_tags,
                           dry_run=dry_run(), page="post",
                           any_ready=any(s["ready"] for s in st.values()),
                           now=datetime.now().strftime("%Y-%m-%dT%H:%M"))


@app.route("/post", methods=["POST"])
def create_post():
    f = request.files.get("file")
    chosen = request.form.getlist("platforms")
    caption = request.form.get("caption", "").strip()
    tags_raw = " ".join(tagslib.parse(request.form.get("tags", "")))
    when = request.form.get("when")
    now = datetime.now().strftime("%Y-%m-%dT%H:%M")
    run_at = request.form.get("run_at") or now

    if not f or not f.filename:
        flash("خاصك تختار صورة أو فيديو", "error")
        return redirect(url_for("index"))
    ext = os.path.splitext(f.filename)[1].lower()
    if ext in IMAGE_EXT:
        media_type = "image"
    elif ext in VIDEO_EXT:
        media_type = "video"
    else:
        flash("الصيغة ماشي مقبولة. استعمل jpg/png/webp أو mp4/mov", "error")
        return redirect(url_for("index"))

    st = platforms.status()
    usable = [p for p in chosen if p in st and st[p]["ready"] and media_type in st[p]["media"]]
    skipped = [st[p]["label"] for p in chosen if p in st and p not in usable]
    if not usable:
        flash("حتى منصة من اللي اخترتي ما كتقبل هاد النوع ولا ماشي مربوطة", "error")
        return redirect(url_for("index"))

    name = f"{uuid.uuid4().hex}{ext}"
    f.save(os.path.join(config.UPLOADS, name))

    with db() as con:
        cur = con.execute(
            "INSERT INTO posts(file, media_type, caption, tags, run_at, created_at, status) VALUES(?,?,?,?,?,?,?)",
            (name, media_type, caption, tags_raw, run_at if when == "later" else now, now, "scheduled"))
        pid = cur.lastrowid
        for p in usable:
            con.execute("INSERT INTO results(post_id, platform, status, detail) VALUES(?,?,?,?)",
                        (pid, p, "pending", ""))

    if when == "later":
        flash(f"تبرمج المنشور لـ {run_at.replace('T', ' ')} — خلي البرنامج مفتوح", "ok")
    else:
        threading.Thread(target=publish_now, args=(pid,), daemon=True).start()
        flash("بدا النشر… الصفحة غادي تتحدث بوحدها", "ok")
    if skipped:
        flash("تزادو هاد المنصات (ماشي مربوطة أو ما كتقبلش هاد النوع): " + "، ".join(skipped), "error")
    return redirect(url_for("index"))


@app.route("/cancel/<int:pid>", methods=["POST"])
def cancel(pid):
    with db() as con:
        con.execute("UPDATE posts SET status='cancelled' WHERE id=? AND status='scheduled'", (pid,))
        con.execute("UPDATE results SET status='cancelled' WHERE post_id=? AND status='pending'", (pid,))
    return redirect(url_for("index"))


@app.route("/retry/<int:pid>", methods=["POST"])
def retry(pid):
    """عاود النشر غير فالمنصات اللي فشلات"""
    with db() as con:
        n = con.execute("UPDATE results SET status='pending', detail='' WHERE post_id=? AND status='error'",
                        (pid,)).rowcount
    if n:
        threading.Thread(target=publish_now, args=(pid,), daemon=True).start()
        flash("كنعاودو النشر فالمنصات اللي فشلات…", "ok")
    return redirect(url_for("index"))


@app.route("/api/busy")
def busy():
    with db() as con:
        n = con.execute("SELECT COUNT(*) FROM posts WHERE status='running'").fetchone()[0]
    return {"running": n}


@app.route("/media/<path:name>")
def media(name):
    """باش Instagram يقدر ياخد الملف من رابط عمومي"""
    return send_from_directory(config.UPLOADS, name)


# ---------------- صفحة الإعدادات ----------------
@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        new = {}
        for group in config.FIELDS.values():
            for key, _, kind, _ in group["fields"]:
                if kind == "bool":
                    new[key] = "1" if request.form.get(key) else "0"
                else:
                    new[key] = request.form.get(key, "")
        data = config.save(new)
        try:
            config.set_start_with_windows(data.get("START_WITH_WINDOWS") == "1")
        except Exception as e:
            flash(f"ما قدرتش نبدل التشغيل التلقائي: {e}", "error")

        secret = request.files.get("client_secret")
        if secret and secret.filename:
            secret.save(config.YOUTUBE_SECRET)
            flash("تحفظ client_secret.json — دابا ضغط على «ربط YouTube»", "ok")
        flash("تحفظات الإعدادات ✓", "ok")
        return redirect(url_for("settings"))

    return render_template("settings.html", groups=config.FIELDS, values=config.load(),
                           status=platforms.status(), page="settings",
                           yt_secret=os.path.exists(config.YOUTUBE_SECRET),
                           yt_token=os.path.exists(config.YOUTUBE_TOKEN),
                           yt_msg=youtube_state["msg"], data_dir=config.DATA_DIR,
                           tt_token=os.path.exists(config.TIKTOK_TOKEN), tt_msg=tiktok_state["msg"])


@app.route("/youtube/connect", methods=["POST"])
def youtube_connect():
    if not os.path.exists(config.YOUTUBE_SECRET):
        flash("طلع client_secret.json أولا", "error")
        return redirect(url_for("settings"))

    # Google كترجع الجواب للبرنامج نيت (نفس البورت ديال البرنامج)
    import webbrowser
    from google_auth_oauthlib.flow import Flow
    os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # عادي: الرابط محلي فالحاسوب فقط
    flow = Flow.from_client_secrets_file(
        config.YOUTUBE_SECRET,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
        redirect_uri=f"http://127.0.0.1:{request.host.split(':')[-1]}/youtube/callback")
    auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")
    youtube_state.update(flow=flow, state=state, msg="تحل المتصفح… دخل لحسابك ووافق")
    webbrowser.open(auth_url)
    flash("تحل المتصفح: اختار الحساب ديالك ووافق، ومن بعد رجع لهنا", "ok")
    return redirect(url_for("settings"))


@app.route("/youtube/callback")
def youtube_callback():
    flow = youtube_state.get("flow")
    page = ("<html dir=rtl><body style='font-family:Segoe UI,Tahoma;text-align:center;padding:60px'>"
            "<h2>{}</h2><p>{}</p></body></html>")
    if not flow or request.args.get("state") != youtube_state.get("state"):
        return page.format("❌ الرابط تسالا", "رجع للبرنامج وضغط «ربط YouTube» من جديد.")
    if request.args.get("error"):
        youtube_state["msg"] = f"تلغى الربط: {request.args['error']}"
        return page.format("❌ ما تمش الربط", "رجع للبرنامج وعاود.")
    try:
        flow.fetch_token(code=request.args.get("code"))
        with open(config.YOUTUBE_TOKEN, "w") as f:
            f.write(flow.credentials.to_json())
        youtube_state.update(flow=None, msg="YouTube مربوط ✓")
        return page.format("✅ تم ربط YouTube", "تقدر تسد هاد الصفحة وترجع للبرنامج SocialPoster.")
    except Exception as e:
        youtube_state["msg"] = f"فشل الربط: {e}"
        return page.format("❌ فشل الربط", str(e))


@app.route("/api/youtube")
def youtube_status():
    return {"connected": os.path.exists(config.YOUTUBE_TOKEN), "pending": bool(youtube_state.get("flow")),
            "tiktok": os.path.exists(config.TIKTOK_TOKEN)}


@app.route("/youtube/disconnect", methods=["POST"])
def youtube_disconnect():
    if os.path.exists(config.YOUTUBE_TOKEN):
        os.remove(config.YOUTUBE_TOKEN)
    youtube_state["msg"] = ""
    return redirect(url_for("settings"))


# ---------------- Facebook و Instagram (كل واحد بوحدو) ----------------
META_API = "https://graph.facebook.com/v21.0"


def _meta_pages(token_field):
    """كياخد التوكن القصير، كيحولو لطويل، وكيرجع الصفحات (مع Instagram المربوط بكل وحدة)"""
    import requests as rq
    app_id = request.form.get("FB_APP_ID", "").strip() or os.getenv("FB_APP_ID", "")
    secret = request.form.get("FB_APP_SECRET", "").strip() or os.getenv("FB_APP_SECRET", "")
    short = request.form.get(token_field, "").strip()
    if not (app_id and secret):
        raise RuntimeError("عمر App ID و App Secret فـ «تطبيق Meta» أولا")
    if not short:
        raise RuntimeError("لصق التوكن من Graph API Explorer")
    config.save({"FB_APP_ID": app_id, "FB_APP_SECRET": secret})
    j = rq.get(f"{META_API}/oauth/access_token", timeout=30, params={
        "grant_type": "fb_exchange_token", "client_id": app_id,
        "client_secret": secret, "fb_exchange_token": short}).json()
    if "access_token" not in j:
        raise RuntimeError(j.get("error", {}).get("message", j))
    pages = rq.get(f"{META_API}/me/accounts", timeout=30, params={
        "fields": "id,name,access_token,instagram_business_account{id,username}",
        "access_token": j["access_token"]}).json()
    if "error" in pages:
        raise RuntimeError(pages["error"].get("message"))
    pages = pages.get("data", [])
    if not pages:
        raise RuntimeError("ما لقيت حتى صفحة. تأكد من pages_show_list وأنك اخترتي الصفحة ملي وافقتي")
    return pages


@app.route("/facebook/connect", methods=["POST"])
def facebook_connect():
    try:
        pages = _meta_pages("fb_user_token")
        page = next((p for p in pages if p["id"] == os.getenv("FB_PAGE_ID", "")), pages[0])
        config.save({"FB_PAGE_ID": page["id"], "FB_PAGE_ACCESS_TOKEN": page["access_token"],
                     "FB_PAGE_NAME": page["name"]})
        msg = f"Facebook: تربطات الصفحة «{page['name']}» ✓"
        if len(pages) > 1:
            msg += " · صفحات أخرى: " + "، ".join(p["name"] for p in pages if p is not page)
        flash(msg, "ok")
    except Exception as e:
        flash(f"Facebook: فشل الربط — {e}", "error")
    return redirect(url_for("settings"))


@app.route("/instagram/connect", methods=["POST"])
def instagram_connect():
    try:
        pages = [p for p in _meta_pages("ig_user_token") if p.get("instagram_business_account")]
        if not pages:
            raise RuntimeError("ما لقيت حتى حساب Instagram Professional مربوط بشي صفحة ديالك "
                               "(ولا نسيتي instagram_basic / business_management)")
        page = next((p for p in pages if p["instagram_business_account"]["id"] == os.getenv("IG_USER_ID", "")), pages[0])
        ig = page["instagram_business_account"]
        config.save({"IG_USER_ID": ig["id"], "IG_USERNAME": ig.get("username", ""),
                     "IG_PAGE_ID": page["id"], "IG_PAGE_TOKEN": page["access_token"]})
        msg = f"Instagram: تربط @{ig.get('username')} ✓"
        if len(pages) > 1:
            msg += " · حسابات أخرى: " + "، ".join("@" + p["instagram_business_account"].get("username", "")
                                                  for p in pages if p is not page)
        flash(msg, "ok")
    except Exception as e:
        flash(f"Instagram: فشل الربط — {e}", "error")
    return redirect(url_for("settings"))


@app.route("/facebook/disconnect", methods=["POST"])
def facebook_disconnect():
    config.save({"FB_PAGE_ID": "", "FB_PAGE_ACCESS_TOKEN": "", "FB_PAGE_NAME": ""})
    if not os.getenv("IG_PAGE_TOKEN"):  # النسخ القديمة: Instagram كان كيستعمل التوكن ديال Facebook
        config.save({"IG_USER_ID": ""})
    return redirect(url_for("settings"))


@app.route("/instagram/disconnect", methods=["POST"])
def instagram_disconnect():
    config.save({"IG_USER_ID": "", "IG_USERNAME": "", "IG_PAGE_ID": "", "IG_PAGE_TOKEN": ""})
    return redirect(url_for("settings"))


# ---------------- TikTok ----------------
tiktok_state = {"state": None, "msg": ""}


@app.route("/tiktok/connect", methods=["POST"])
def tiktok_connect():
    import secrets
    import webbrowser
    from urllib.parse import urlencode
    key, redirect_uri = os.getenv("TIKTOK_CLIENT_KEY"), os.getenv("TIKTOK_REDIRECT_URI", "").strip()
    if not key or not os.getenv("TIKTOK_CLIENT_SECRET") or not redirect_uri:
        flash("عمر Client key و Client secret و Redirect URI وضغط حفظ أولا", "error")
        return redirect(url_for("settings"))
    state = secrets.token_urlsafe(16)
    tiktok_state.update(state=state, msg="تحل المتصفح… دخل لحساب TikTok ووافق")
    webbrowser.open("https://www.tiktok.com/v2/auth/authorize/?" + urlencode({
        "client_key": key, "response_type": "code", "scope": platforms.tiktok.SCOPES,
        "redirect_uri": redirect_uri, "state": state}))
    flash("تحل المتصفح: دخل لحساب TikTok ووافق، ومن بعد رجع لهنا", "ok")
    return redirect(url_for("settings"))


@app.route("/tiktok/callback")
def tiktok_callback():
    page = ("<html dir=rtl><body style='font-family:Segoe UI,Tahoma;text-align:center;padding:60px'>"
            "<h2>{}</h2><p>{}</p></body></html>")
    if not tiktok_state["state"] or request.args.get("state") != tiktok_state["state"]:
        return page.format("❌ الرابط تسالا", "رجع للبرنامج وضغط «ربط TikTok» من جديد.")
    if request.args.get("error"):
        tiktok_state["msg"] = f"تلغى الربط: {request.args.get('error_description') or request.args['error']}"
        return page.format("❌ ما تمش الربط", tiktok_state["msg"])
    try:
        platforms.tiktok.exchange_code(request.args.get("code"), os.getenv("TIKTOK_REDIRECT_URI", "").strip())
        tiktok_state.update(state=None, msg="TikTok مربوط ✓")
        return page.format("✅ تم ربط TikTok", "تقدر تسد هاد الصفحة وترجع للبرنامج SocialPoster.")
    except Exception as e:
        tiktok_state["msg"] = f"فشل الربط: {e}"
        return page.format("❌ فشل الربط", str(e))


@app.route("/tiktok/disconnect", methods=["POST"])
def tiktok_disconnect():
    if os.path.exists(config.TIKTOK_TOKEN):
        os.remove(config.TIKTOK_TOKEN)
    tiktok_state["msg"] = ""
    return redirect(url_for("settings"))


@app.route("/open-data")
def open_data():
    """كيحل الدوسي فين محفوظين الملفات"""
    if hasattr(os, "startfile"):
        os.startfile(config.DATA_DIR)
    return redirect(url_for("settings"))
