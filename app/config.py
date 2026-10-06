import os
from datetime import timedelta


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in {"1", "true", "yes", "on"}


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except (TypeError, ValueError):
        return default


def _normalize_db_url(url: str | None) -> str | None:
    """Render/Heroku/Railway provide postgresql:// URLs which default to
    psycopg2 in SQLAlchemy. We use psycopg (v3), so rewrite the scheme."""
    if not url:
        return url
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class BaseConfig:
    # ── Flask core ──────────────────────────────────────
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-only-not-for-production")
    SERVER_NAME = os.getenv("SERVER_NAME") or None
    PREFERRED_URL_SCHEME = "https"
    ENV = os.getenv("FLASK_ENV", "development")

    # ── Sessions / cookies ──────────────────────────────
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_SAMESITE = "Lax"

    # ── SQLAlchemy ──────────────────────────────────────
    # Pool sizing rationale:
    #   We run 1 Gunicorn worker with 4 threads on Render's free tier.
    #   That is 4 concurrent request slots per process.
    #   pool_size=3 leaves room for one non-request connection (migrations,
    #   shell work) while still allowing headroom above typical concurrent
    #   throughput. max_overflow=2 absorbs short bursts but no more.
    #   Total ceiling per process: 5 connections.
    #   Render free Postgres allows ~22 concurrent connections; two
    #   processes (web + occasional shell) = 10, well under the cap.
    #   pool_timeout=10 prevents worker threads from waiting 30s for a slot
    #   before failing.
    #   pool_recycle=280 stays below Render's own idle-connection reaper
    #   (~5 minutes), so we never hand a dead connection to a request.
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(os.getenv("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_size": _int("SQLALCHEMY_POOL_SIZE", 3),
        "max_overflow": _int("SQLALCHEMY_MAX_OVERFLOW", 2),
        "pool_timeout": _int("SQLALCHEMY_POOL_TIMEOUT", 10),
        "pool_recycle": _int("SQLALCHEMY_POOL_RECYCLE", 280),
    }

    # ── Redis / Celery ──────────────────────────────────
    REDIS_URL = os.getenv("REDIS_URL", "")
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "memory://")
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "cache+memory://")

    # ── Rate limiting ───────────────────────────────────
    # If REDIS_URL is set, Flask-Limiter uses Redis (required for
    # multi-process correctness). Otherwise it uses in-memory storage,
    # which is fine for a single-process dev instance but NOT safe in
    # production with multiple workers.
    RATELIMIT_ENABLED = _bool("RATELIMIT_ENABLED", True)
    RATELIMIT_STORAGE_URI = os.getenv("REDIS_URL") or "memory://"
    RATELIMIT_DEFAULT = "300 per hour"
    RATELIMIT_HEADERS_ENABLED = True

    # ── CSRF ────────────────────────────────────────────
    WTF_CSRF_TIME_LIMIT = None

    # ── Uploads ─────────────────────────────────────────
    MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # 5 MB

    # ── Branding ────────────────────────────────────────
    DEFAULT_UNIVERSITY_SLUG = os.getenv("DEFAULT_UNIVERSITY_SLUG", "unilorin")

    # ── Mapbox ──────────────────────────────────────────
    MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN", "")
    POSTGIS_ENABLED = _bool("POSTGIS_ENABLED", True)

    # ── Cloudflare R2 ───────────────────────────────────
    R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "")
    R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "")
    R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "")
    R2_BUCKET = os.getenv("R2_BUCKET", "")
    R2_PUBLIC_BASE_URL = os.getenv("R2_PUBLIC_BASE_URL", "")

    # ── Sentry (optional) ───────────────────────────────
    SENTRY_DSN = os.getenv("SENTRY_DSN", "")


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    TEMPLATES_AUTO_RELOAD = True


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    RATELIMIT_ENABLED = False
    SQLALCHEMY_DATABASE_URI = _normalize_db_url(
        os.getenv("TEST_DATABASE_URL",
                  "postgresql+psycopg://campusos:campusos@localhost:5432/campusos_test")
    )


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True


_CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}


def get_config(name: str | None = None):
    name = name or os.getenv("FLASK_ENV", "development")
    return _CONFIGS.get(name, DevelopmentConfig)