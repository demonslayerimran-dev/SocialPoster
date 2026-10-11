"""
نقطة البداية ديال التطبيق فـ Windows.
كيشغل السيرفر الداخلي، والجدولة، ومن بعد كيحل نافذة ديال البرنامج.
"""
import socket
import sys
import threading

import webview
from apscheduler.schedulers.background import BackgroundScheduler
from waitress import serve

import app as server

PORT = 51791  # ثابت: باش ngrok (لـ Instagram) يبقى على نفس البورت


def already_running():
    s = socket.socket()
    try:
        s.bind(("127.0.0.1", PORT))
        return False
    except OSError:
        return True
    finally:
        s.close()


def main():
    if already_running():
        # البرنامج ديجا مفتوح: نوريو غير رسالة ونخرجو
        webview.create_window("SocialPoster", html="<p dir=rtl style='font-family:Segoe UI;padding:20px'>"
                              "البرنامج ديجا مفتوح فشي نافذة أخرى.</p>", width=360, height=140)
        webview.start()
        return

    server.init_db()
    sched = BackgroundScheduler()
    sched.add_job(server.check_due, "interval", seconds=30)
    sched.start()

    threading.Thread(target=serve, args=(server.app,),
                     kwargs={"host": "127.0.0.1", "port": PORT, "threads": 8}, daemon=True).start()

    window = webview.create_window(
        "SocialPoster — نشر فكل المنصات",
        f"http://127.0.0.1:{PORT}/",
        width=1100, height=820, min_size=(720, 560),
        minimized="--minimized" in sys.argv,
    )

    def on_closing():
        n = server.pending_count()
        if n:
            return window.create_confirmation_dialog(
                "متأكد؟",
                f"عندك {n} منشور مبرمج. إلا سديتي البرنامج ما غادي يتنشروش حتى تعاود تحلو.\n\nبغيتي تسد؟")
        return True

    window.events.closing += on_closing
    webview.start()
    sched.shutdown(wait=False)


if __name__ == "__main__":
    main()
