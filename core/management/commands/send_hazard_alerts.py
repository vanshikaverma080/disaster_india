from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
from django.db import close_old_connections
from datetime import timedelta
import hashlib

from core.models import AlertSubscription
from core.services import hazard_snapshot, DISTRICT_SEEDS

HAZARDS=("flood","earthquake","fire","sealevel")

class Command(BaseCommand):
    help="Check live hazard feeds and email subscribed users when their threshold is crossed."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--email", default="")
        parser.add_argument("--district", default="")

    def handle(self,*args,**opts):
        close_old_connections()
        qs=AlertSubscription.objects.filter(active=True)
        if opts["email"]: qs=qs.filter(email=opts["email"].strip().lower())
        if opts["district"]: qs=qs.filter(district__iexact=opts["district"].strip())
        sent=0; checked=0
        cache={}
        for sub in qs:
            district_names=[sub.district] if sub.district else [x[0] for x in DISTRICT_SEEDS]
            for name in district_names:
                checked+=1
                try:
                    snap=cache.get(name)
                    if snap is None:
                        snap=hazard_snapshot(name); cache[name]=snap
                    if not snap: continue
                    triggered=[]
                    for hazard in (sub.hazards or list(HAZARDS)):
                        value=float(snap.get(hazard,0) or 0)
                        if value >= float(sub.threshold):
                            triggered.append((hazard,value))
                    if not triggered: continue
                    key=hashlib.sha256((name+"|"+str([(h,round(v,3)) for h,v in triggered])+"|"+str(sub.threshold)).encode()).hexdigest()[:32]
                    if sub.last_alert_key==key and sub.last_alert_at and timezone.now()-sub.last_alert_at < timedelta(minutes=settings.ALERT_COOLDOWN_MINUTES):
                        continue
                    highest=max(v for _,v in triggered)
                    level="CRITICAL" if highest>=.85 else "HIGH" if highest>=.70 else "WATCH"
                    subject=f"ClimateGuard {level} · {name} · {', '.join(h.title() for h,_ in triggered)}"
                    lines=[
                        f"ClimateGuard {level} hazard notice for {name}.",
                        "",
                        "Why you are receiving this:",
                        f"Your subscription threshold is {sub.threshold*100:.0f}%, and one or more monitored hazards crossed it.",
                        "",
                        "Current signals:",
                    ]
                    for hazard,value in triggered:
                        lines.append(f"- {hazard.title()}: {value*100:.0f}% risk")
                    lines += [
                        "",
                        "Suggested next steps:",
                        "- Check the ClimateGuard dashboard for live weather, hazard details, and nearby route/resource suggestions.",
                        "- Keep phone, documents, medicines, water, and emergency contacts ready if conditions worsen.",
                        "- Follow IMD, NDMA, state disaster management, police, fire, medical, and local authority instructions.",
                        "",
                        "Important: this is a decision-support notification, not an official emergency warning.",
                        f"Dashboard: {settings.CLIMATEGUARD_BASE_URL}",
                        f"Unsubscribe: {settings.CLIMATEGUARD_BASE_URL}/api/alerts/unsubscribe?token={sub.unsubscribe_token}",
                    ]
                    if opts["dry_run"]:
                        self.stdout.write(f"[DRY RUN] {sub.email} <- {subject}")
                    else:
                        msg=EmailMultiAlternatives(subject, "\n".join(lines), settings.DEFAULT_FROM_EMAIL,[sub.email])
                        msg.send(fail_silently=False)
                    sub.last_alert_key=key; sub.last_alert_at=timezone.now(); sub.save(update_fields=["last_alert_key","last_alert_at","updated_at"])
                    sent+=1
                except Exception as exc:
                    self.stderr.write(f"{name} / {sub.email}: {exc}")
        self.stdout.write(self.style.SUCCESS(f"Checked {checked} subscription/district pairs; sent {sent} alert(s)."))
