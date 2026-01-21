import os
from pathlib import Path
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "django-insecure-default-key")

DEBUG = True

ALLOWED_HOSTS = ["*"]

# =============================
# Applications
# =============================
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",

    "core.apps.CoreConfig",
    "shop.apps.ShopConfig",
    "customers.apps.CustomersConfig",
    "reports.apps.ReportsConfig",
    "alertpay.apps.AlertPayConfig",

    "django_extensions",
    "django_celery_beat",
]

AUTH_USER_MODEL = "core.User"

# =============================
# Middleware
# =============================
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# =============================
# CORS
# =============================
CORS_ALLOW_ALL_ORIGINS = True

CORS_ALLOW_METHODS = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]

CORS_ALLOW_HEADERS = [
    "content-type",
    "authorization",
    "accept",
    "x-csrftoken",
]

# =============================
# URLs / Templates
# =============================
ROOT_URLCONF = "shop_manager_backend.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "shop_manager_backend.wsgi.application"

# =============================
# DATABASE (SQLite local | Neon on Render)
# =============================
DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    # Render / Neon (PostgreSQL)
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=True,
        )
    }
else:
    # Local development (SQLite)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# =============================
# Password Validators
# =============================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# =============================
# DRF
# =============================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.FormParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp-relay.brevo.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

# SMTP key इस्तेमाल करें (API key नहीं!)
# Brevo → SMTP & API → SMTP tab → Generate new SMTP key
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = 'geetagalaxyadvertising2002@gmail.com'   # Brevo में verified होना चाहिए
SERVER_EMAIL = 'geetagalaxyadvertising2002@gmail.com'
BREVO_API_KEY = os.getenv("BREVO_API_KEY")

# =============================
# Celery
# =============================
CELERY_BROKER_URL = "redis://localhost:6379/0"
CELERY_RESULT_BACKEND = "redis://localhost:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "Asia/Kolkata"

CELERY_BEAT_SCHEDULE = {
    "check-due-sales-every-minute": {
        "task": "shop.tasks.notify_due_sales",
        "schedule": 60.0,
    }
}

# =============================
# Email
# =============================

# =============================
# Misc
# =============================
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# =============================
# Logging
# =============================
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": True,
        },
    },
}
