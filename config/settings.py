from pathlib import Path
import os
from dotenv import load_dotenv
load_dotenv()
BASE_DIR=Path(__file__).resolve().parent.parent
SECRET_KEY=os.getenv("DJANGO_SECRET_KEY","dev-only-change-me")
DEBUG=os.getenv("DJANGO_DEBUG","True").lower()=="true"
ALLOWED_HOSTS=[x.strip() for x in os.getenv("DJANGO_ALLOWED_HOSTS","127.0.0.1,localhost").split(",") if x.strip()]
INSTALLED_APPS=[
 "django.contrib.admin","django.contrib.auth","django.contrib.contenttypes",
 "django.contrib.sessions","django.contrib.messages","django.contrib.staticfiles",
 "corsheaders","rest_framework","core.apps.CoreConfig",
]
MIDDLEWARE=[
 "django.middleware.security.SecurityMiddleware","corsheaders.middleware.CorsMiddleware",
 "django.contrib.sessions.middleware.SessionMiddleware","django.middleware.common.CommonMiddleware",
 "django.middleware.csrf.CsrfViewMiddleware","django.contrib.auth.middleware.AuthenticationMiddleware",
 "django.contrib.messages.middleware.MessageMiddleware","django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF="config.urls"
TEMPLATES=[{"BACKEND":"django.template.backends.django.DjangoTemplates","DIRS":[BASE_DIR/"templates"],"APP_DIRS":True,"OPTIONS":{"context_processors":[
 "django.template.context_processors.request","django.contrib.auth.context_processors.auth",
 "django.contrib.messages.context_processors.messages"]}}]
WSGI_APPLICATION="config.wsgi.application"
DATABASES={"default":{"ENGINE":"django.db.backends.sqlite3","NAME":BASE_DIR/"climateguard.sqlite3"}}
AUTH_PASSWORD_VALIDATORS=[]
LANGUAGE_CODE="en-us"; TIME_ZONE="Asia/Kolkata"; USE_I18N=True; USE_TZ=True
STATIC_URL="/static/"; STATICFILES_DIRS=[BASE_DIR/"static"]
DEFAULT_AUTO_FIELD="django.db.models.BigAutoField"
CORS_ALLOW_ALL_ORIGINS=os.getenv("CORS_ALLOW_ALL_ORIGINS","False").lower()=="true"
CORS_ALLOWED_ORIGINS=[x.strip() for x in os.getenv("CORS_ALLOWED_ORIGINS","http://127.0.0.1:8000,http://localhost:8000").split(",") if x.strip()]
CSRF_TRUSTED_ORIGINS=["http://127.0.0.1:8000","http://localhost:8000"]
CACHES={"default":{"BACKEND":"django.core.cache.backends.locmem.LocMemCache","LOCATION":"climateguard-cache"}}
LIVE_API_CACHE_SECONDS=int(os.getenv("LIVE_API_CACHE_SECONDS","600"))
LIVE_API_TIMEOUT_SECONDS=float(os.getenv("LIVE_API_TIMEOUT_SECONDS","6"))
CHAT_RATE_LIMIT_PER_MINUTE=int(os.getenv("CHAT_RATE_LIMIT_PER_MINUTE","12"))
CHAT_TIMEOUT_SECONDS=float(os.getenv("CHAT_TIMEOUT_SECONDS","15"))


# Email alert delivery. Configure these in backend/.env.
EMAIL_BACKEND=os.getenv("EMAIL_BACKEND","django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST=os.getenv("EMAIL_HOST","smtp.gmail.com")
EMAIL_PORT=int(os.getenv("EMAIL_PORT","587"))
EMAIL_HOST_USER=os.getenv("EMAIL_HOST_USER","vvanshika135@gmail.com")
EMAIL_HOST_PASSWORD=os.getenv("EMAIL_HOST_PASSWORD","mttr tqjd kuxj eneg")
EMAIL_USE_TLS=os.getenv("EMAIL_USE_TLS","True").lower()=="true"
DEFAULT_FROM_EMAIL=os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "ClimateGuard <alerts@localhost>")
CLIMATEGUARD_BASE_URL=os.getenv("CLIMATEGUARD_BASE_URL","http://127.0.0.1:8000")
ALERT_COOLDOWN_MINUTES=int(os.getenv("ALERT_COOLDOWN_MINUTES","180"))
ALERT_AUTO_SEND=os.getenv("ALERT_AUTO_SEND","False").lower()=="true"
ALERT_CHECK_INTERVAL_SECONDS=int(os.getenv("ALERT_CHECK_INTERVAL_SECONDS","900"))
