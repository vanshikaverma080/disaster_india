# ClimateGuard Accounts + Subscriptions + Alerts

## 1. Install

```bash
python -m venv venv
# Windows
venv\\Scripts\\activate
# Linux/macOS
source venv/bin/activate
pip install -r requirements.txt
```

## 2. Database

```bash
python manage.py migrate
python manage.py createsuperuser
```

Migration `0003_alertsubscription_user.py` connects alert subscriptions to Django accounts while retaining email-based subscriptions.

## 3. Gmail automatic email alerts

Create `.env` from `.env.example` and set:

```env
DJANGO_SECRET_KEY=replace-with-a-random-secret
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost

EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=yourgmail@gmail.com
EMAIL_HOST_PASSWORD=your-16-character-gmail-app-password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=ClimateGuard <yourgmail@gmail.com>
CLIMATEGUARD_BASE_URL=http://127.0.0.1:8000
ALERT_COOLDOWN_MINUTES=180
```

For Gmail, use a Google **App Password**, not your normal Gmail password.

## 4. Test alert delivery

First create an account and save a subscription from the Account button.

Then run:

```bash
python manage.py send_hazard_alerts --dry-run
```

To send real email:

```bash
python manage.py send_hazard_alerts
```

For one user/district:

```bash
python manage.py send_hazard_alerts --email user@example.com --district Patna
```

## 5. Run automatically

### Linux / AWS EC2 cron

Run every 15 minutes:

```cron
*/15 * * * * cd /path/to/ClimateGuard-Django && /path/to/venv/bin/python manage.py send_hazard_alerts >> /path/to/climateguard-alerts.log 2>&1
```

### Windows Task Scheduler

Create a task that runs every 15 minutes:

Program:

```text
C:\path\to\ClimateGuard-Django\venv\Scripts\python.exe
```

Arguments:

```text
manage.py send_hazard_alerts
```

Start in:

```text
C:\path\to\ClimateGuard-Django
```

## 6. What now works

- Account registration and login use Django sessions.
- Subscriptions are linked to the logged-in Django user.
- A user can select district, hazards and a risk threshold.
- Active subscriptions can be displayed from the Account window.
- Automatic alert emails use the existing `send_hazard_alerts` management command.
- Duplicate alerts are suppressed by the cooldown/key mechanism.
- Alert emails include an unsubscribe token/link.
- Predict page includes a 12-month Monthly Signal chart.
- Evacuate page uses the backend risk-weighted Dijkstra route and displays route waypoints on a Leaflet map.
- Monthly Signal and evacuation APIs remain separate from authentication, so the public decision-support pages continue to work.

## 7. Start

```bash
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.
