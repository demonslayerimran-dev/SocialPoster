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

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".m4v"}

app = Flask(__name__, template_folder=config.resource_path("templates"))
app.secret_key = uuid.uuid4().hex
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
                detail = mod.post(path, p["media_type"], p["caption"] or "", public_url)
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
    return render_template("index.html", status=st, posts=posts, results=results,
                           dry_run=dry_run(), page="post",
                           any_ready=any(s["ready"] for s in st.values()),
                           now=datetime.now().strftime("%Y-%m-%dT%H:%M"))


@app.route("/post", methods=["POST"])
def create_post():
    f = request.files.get("file")
    chosen = request.form.getlist("platforms")
    caption = request.form.get("caption", "").strip()
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
            "INSERT INTO posts(file, media_type, caption, run_at, created_at, status) VALUES(?,?,?,?,?,?)",
            (name, media_type, caption, run_at if when == "later" else now, now, "scheduled"))
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
                           yt_msg=youtube_state["msg"], data_dir=config.DATA_DIR)


@app.route("/youtube/connect", methods=["POST"])
def youtube_connect():
    if not os.path.exists(config.YOUTUBE_SECRET):
        flash("طلع client_secret.json أولا", "error")
        return redirect(url_for("settings"))

    def run():
        try:
            from google_auth_oauthlib.flow import InstalledAppFlow
            youtube_state["msg"] = "تحل المتصفح… دخل لحسابك ووافق"
            flow = InstalledAppFlow.from_client_secrets_file(
                config.YOUTUBE_SECRET, scopes=["https://www.googleapis.com/auth/youtube.upload"])
            creds = flow.run_local_server(port=0, open_browser=True,
                                          success_message="تم الربط! رجع للبرنامج.")
            with open(config.YOUTUBE_TOKEN, "w") as f:
                f.write(creds.to_json())
            youtube_state["msg"] = "YouTube مربوط ✓"
        except Exception as e:
            youtube_state["msg"] = f"فشل الربط: {e}"

    threading.Thread(target=run, daemon=True).start()
    flash("غادي يتحل المتصفح باش توافق على الربط…", "ok")
    return redirect(url_for("settings"))


@app.route("/youtube/disconnect", methods=["POST"])
def youtube_disconnect():
    if os.path.exists(config.YOUTUBE_TOKEN):
        os.remove(config.YOUTUBE_TOKEN)
    youtube_state["msg"] = ""
    return redirect(url_for("settings"))


@app.route("/open-data")
def open_data():
    """كيحل الدوسي فين محفوظين الملفات"""
    if hasattr(os, "startfile"):
        os.startfile(config.DATA_DIR)
    return redirect(url_for("settings"))
