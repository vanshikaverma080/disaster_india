# ClimateGuard Accounts, Subscriptions, Alerts, Prediction & Evacuation

This build includes:

- Django registration and login using the built-in User model.
- Logout and session authentication.
- Account modal with a visible `×` close button.
- Close account modal by `×`, clicking outside, or pressing Escape.
- Per-user alert subscriptions linked to the Django account.
- Hazard choices: flood, earthquake, fire and sea level.
- District-specific or all-district subscriptions.
- Configurable risk threshold (30%–95%).
- Automatic email alert command with cooldown and unsubscribe token.
- Predict page with ML flood prediction.
- Monthly Signal page/chart with 12-month district risk signal.
- Evacuate page with risk-weighted safest route and Leaflet route map.

## Start

```bash
python -m venv venv
# Windows
venv\\Scripts\\activate
# Linux/macOS
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Open `http://127.0.0.1:8000/`.

## Gmail alerts

Copy `.env.example` to `.env` and configure:

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=yourgmail@gmail.com
EMAIL_HOST_PASSWORD=your-gmail-app-password
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=ClimateGuard <yourgmail@gmail.com>
CLIMATEGUARD_BASE_URL=http://127.0.0.1:8000
ALERT_COOLDOWN_MINUTES=180
```

Test alert processing without sending email:

```bash
python manage.py send_hazard_alerts --dry-run
```

Send real emails:

```bash
python manage.py send_hazard_alerts
```

Schedule the command with Windows Task Scheduler or Linux cron. See `ACCOUNT_ALERT_SETUP.md`.

## Important

Prediction, risk scores and evacuation routes are decision-support estimates. They are not official emergency warnings. During an actual emergency, follow NDMA, IMD, state authorities and local emergency instructions.
