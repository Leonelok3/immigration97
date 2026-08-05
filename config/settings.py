"""
Django settings – IMMIGRATION97
Production Ready – Secure – Optimized
⚠️ Aucun secret ne doit être commité
"""

from pathlib import Path
import os
import sys
from dotenv import load_dotenv
from django.utils.translation import gettext_lazy as _


# ======================================================
# BASE
# ======================================================

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# ======================================================
# SECURITY
# ======================================================

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("DJANGO_SECRET_KEY manquant dans .env")

DEBUG = env_bool("DJANGO_DEBUG", False)
TESTING = "test" in sys.argv

ALLOWED_HOSTS = [
    "immigration97.com",
    "www.immigration97.com",
    "127.0.0.1",
    "localhost",
]

# Permet d'ajouter des hosts via .env
# Ex: DJANGO_ALLOWED_HOSTS="api.immigration97.com,staging.immigration97.com"
_extra_hosts = os.environ.get("DJANGO_ALLOWED_HOSTS", "").strip()
if _extra_hosts:
    for h in [x.strip() for x in _extra_hosts.split(",") if x.strip()]:
        if h not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(h)

CSRF_TRUSTED_ORIGINS = [
    "https://immigration97.com",
    "https://www.immigration97.com",
]

# Ex: DJANGO_CSRF_TRUSTED_ORIGINS="https://staging.immigration97.com"
_extra_csrf = os.environ.get("DJANGO_CSRF_TRUSTED_ORIGINS", "").strip()
if _extra_csrf:
    for o in [x.strip() for x in _extra_csrf.split(",") if x.strip()]:
        if o not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(o)

# Valeurs pilotées par .env (avec fallback safe)
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000" if not DEBUG else "0"))
SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", not DEBUG)
SESSION_COOKIE_SECURE = env_bool("SESSION_COOKIE_SECURE", not DEBUG)
CSRF_COOKIE_SECURE = env_bool("CSRF_COOKIE_SECURE", not DEBUG)

SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# Derrière Nginx/Proxy HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# Option legacy Django (inutile en Django récent, mais non bloquante)
SECURE_BROWSER_XSS_FILTER = True

DEFAULT_DOMAIN = "immigration97.com"
DEFAULT_PROTOCOL = "https"
SITE_ID = 1


# ======================================================
# APPLICATIONS
# ======================================================

INSTALLED_APPS = [
    "edu_platform.apps.EduPlatformConfig",
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "django.contrib.sitemaps",

    # Security / 2FA
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django_otp.plugins.otp_static",
    "two_factor",
    "axes",

    # Third-party
    "whitenoise.runserver_nostatic",
    "widget_tweaks",
    "django_filters",
    "rest_framework",
    "drf_spectacular",
    "csp",
    "corsheaders",

    # Apps internes
    "photos",
    "billing",
    "cv_generator",
    "authentification",
    "MotivationLetterApp",
    "eligibility",
    "core",
    "radar",
    "preparation_tests",
    "visaetude",
    "VisaTravailApp",
    "permanent_residence",
    "EnglishPrepApp.apps.EnglishprepappConfig",
    "GermanPrepApp.apps.GermanprepappConfig",
    "VisaTourismeApp",
    "DocumentsApp",
    "ai_engine",
    "actualite.apps.ActualiteConfig",
    "accounts.apps.AccountsConfig",
    "recruiters",
    "profiles",
    "legal",
    "italian_courses",
    "job_agent",
    "mediafiles",
    "resources",
    "outreach",
    "esignature",
]


# ======================================================
# MIDDLEWARE
# ======================================================

MIDDLEWARE = [
    "edu_platform.middleware.device_lock_middleware.DeviceLockMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "csp.middleware.CSPMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "axes.middleware.AxesMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ======================================================
# TEMPLATES
# ======================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "billing.context_processors.premium_status",
            ],
        },
    },
]


# ======================================================
# DATABASE
# ======================================================

if os.environ.get("USE_POSTGRES", "True") == "True":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("DB_NAME"),
            "USER": os.environ.get("DB_USER"),
            "PASSWORD": os.environ.get("DB_PASSWORD"),
            "HOST": os.environ.get("DB_HOST", "localhost"),
            "PORT": os.environ.get("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }


# ======================================================
# INTERNATIONALISATION
# ======================================================

LANGUAGE_CODE = "fr"
TIME_ZONE = "Africa/Douala"
USE_I18N = True
USE_TZ = True

LANGUAGES = [
    ("fr", _("Français")),
    ("en", _("English")),
    ("de", _("Deutsch")),
    ("it", _("Italiano")),
]

LOCALE_PATHS = [BASE_DIR / "locale"]


# ======================================================
# STATIC & MEDIA
# ======================================================

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG or TESTING
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))

PROTECTED_MEDIA_URL = "/protected-media/"
PROTECTED_MEDIA_ROOT = Path(
    os.environ.get("DJANGO_PROTECTED_MEDIA_ROOT", str(BASE_DIR / "media" / "protected-media"))
)

FILE_UPLOAD_PERMISSIONS = 0o640
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE", str(25 * 1024 * 1024)))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE", str(10 * 1024 * 1024)))


# ======================================================
# EMAIL – HOSTINGER
# ======================================================

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.hostinger.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_USE_TLS = True
EMAIL_USE_SSL = False
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "Immigration97 <contact@immigration97.com>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL
EMAIL_TIMEOUT = 10


# ======================================================
# PAYMENTS
# ======================================================
NOTCHPAY_PUBLIC_KEY = os.environ.get("NOTCHPAY_PUBLIC_KEY", "")
NOTCHPAY_HASH_KEY = os.environ.get("NOTCHPAY_HASH_KEY", "")

PAYUNIT_API_USERNAME = os.environ.get("PAYUNIT_API_USERNAME", "")
PAYUNIT_API_PASSWORD = os.environ.get("PAYUNIT_API_PASSWORD", "")
PAYUNIT_API_KEY = os.environ.get("PAYUNIT_API_KEY", "")
PAYUNIT_MODE = os.environ.get("PAYUNIT_MODE", "test").strip().lower()
PAYUNIT_CURRENCY = os.environ.get("PAYUNIT_CURRENCY", "XAF")
PAYUNIT_AVAILABLE = all([PAYUNIT_API_USERNAME, PAYUNIT_API_PASSWORD, PAYUNIT_API_KEY])

# ======================================================
# OPENAI / AI SERVICE
# ======================================================

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_TIMEOUT_SECONDS = int(os.environ.get("OPENAI_TIMEOUT_SECONDS", "30"))

# ======================================================
# AUTH
# ======================================================

LOGIN_URL = "authentification:login"
LOGIN_REDIRECT_URL = "/profiles/"
LOGOUT_REDIRECT_URL = "home"

AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AXES_ENABLED = True
AXES_FAILURE_LIMIT = 5
AXES_LOCK_OUT_AT_FAILURE = True
AXES_COOLOFF_TIME = 1


# ======================================================
# CSP
# ======================================================

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ("'self'",),
        "connect-src": ("'self'",),
        "font-src": ("'self'", "https://fonts.gstatic.com", "data:"),
        "frame-src": ("'self'",),
        "img-src": (
            "'self'",
            "data:",
            "https://res.cloudinary.com",
        ),
        "script-src": (
            "'self'",
            "https://cdnjs.cloudflare.com",
            "'unsafe-inline'",
            "'unsafe-eval'",
        ),
        "style-src": ("'self'", "https://fonts.googleapis.com", "'unsafe-inline'"),
    }
}


# ======================================================
# LOGGING
# ======================================================

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "file": {
            "level": "ERROR",
            "class": "logging.FileHandler",
            "filename": LOG_DIR / "django-error.log",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["file"],
            "level": "ERROR",
            "propagate": True,
        },
    },
}


# ======================================================
# CORS / COOKIES
# ======================================================

CORS_ALLOWED_ORIGINS = [
    "https://fr.indeed.com",
    "https://www.indeed.com",
    "https://immigration97.com",
    "https://www.immigration97.com",
]

if DEBUG:
    CORS_ALLOWED_ORIGINS += [
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGIN_REGEXES = [r"^chrome-extension://.*$"]

# SameSite seulement
if DEBUG:
    SESSION_COOKIE_SAMESITE = "Lax"
    CSRF_COOKIE_SAMESITE = "Lax"
else:
    SESSION_COOKIE_SAMESITE = "None"
    CSRF_COOKIE_SAMESITE = "None"


# ======================================================
# DRF / OPENAPI
# ======================================================

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Immigration97 API",
    "DESCRIPTION": "API documentation",
    "VERSION": "1.0.0",
    "DISABLE_ERRORS_AND_WARNINGS": True,
}


# ======================================================
# DIVERS
# ======================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
# ── EduCam Pro ────────────────────────────────────────────────
import os as _os
EDU_PLATFORM = {
    'SITE_NAME': 'EduCam Pro',
    'ORANGE_MONEY_API_KEY': _os.getenv('ORANGE_MONEY_API_KEY', ''),
    'ORANGE_MONEY_SECRET': _os.getenv('ORANGE_MONEY_SECRET', ''),
    'MTN_MOMO_SUBSCRIPTION_KEY': _os.getenv('MTN_MOMO_SUBSCRIPTION_KEY', ''),
    'MTN_MOMO_API_USER': _os.getenv('MTN_MOMO_API_USER', ''),
    'MTN_MOMO_API_KEY': _os.getenv('MTN_MOMO_API_KEY', ''),
    'MTN_MOMO_ENVIRONMENT': _os.getenv('MTN_MOMO_ENVIRONMENT', 'sandbox'),
    'WEBHOOK_HMAC_SECRET': _os.getenv('EDU_WEBHOOK_HMAC_SECRET', 'changeme'),
    'MAX_DEVICES_PER_CODE': 1,
    'ACCESS_TOKEN_EXPIRY_MINUTES': 15,
}
SITE_URL = _os.getenv('SITE_URL', 'https://immigration97.com')
