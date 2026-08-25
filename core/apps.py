import os
import sys
import threading
import time

from django.apps import AppConfig
from django.conf import settings
from django.core.management import call_command


_scheduler_started = False


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        global _scheduler_started
        if _scheduler_started or not getattr(settings, "ALERT_AUTO_SEND", False):
            return
        if any(cmd in sys.argv for cmd in ["test", "migrate", "makemigrations", "collectstatic", "shell"]):
            return
        if "runserver" in sys.argv and os.environ.get("RUN_MAIN") != "true":
            return
        _scheduler_started = True
        thread = threading.Thread(target=_alert_loop, name="climateguard-alert-scheduler", daemon=True)
        thread.start()


def _alert_loop():
    interval = max(60, int(getattr(settings, "ALERT_CHECK_INTERVAL_SECONDS", 900)))
    time.sleep(10)
    while True:
        try:
            call_command("send_hazard_alerts")
        except Exception:
            pass
        time.sleep(interval)
