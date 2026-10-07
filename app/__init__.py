from dotenv import load_dotenv
load_dotenv()

import logging
from flask import Flask, jsonify, request, redirect, url_for, flash
from sqlalchemy import text

from app.config import get_config
from app.extensions import db, migrate, login_manager, csrf, limiter


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)

    # ── Config ──────────────────────────────────────────
    cfg = get_config(config_name)
    app.config.from_object(cfg)

    # ── Logging ─────────────────────────────────────────
    if app.config.get("ENV") == "production":
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s %(levelname)s %(name)s %(message)s',
        )
    else:
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s %(levelname)s %(name)s %(message)s',
        )

    # ── Sentry (optional) ───────────────────────────────
    dsn = app.config.get("SENTRY_DSN")
    if dsn:
        try:
            import sentry_sdk
            from sentry_sdk.integrations.flask import FlaskIntegration
            sentry_sdk.init(
                dsn=dsn,
                integrations=[FlaskIntegration()],
                traces_sample_rate=0.1,
                environment=app.config.get("ENV", "development"),
            )
            app.logger.info("Sentry initialized.")
        except ImportError:
            app.logger.warning("SENTRY_DSN set but sentry-sdk not installed; skipping.")

    # ── Extensions ──────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    @login_manager.unauthorized_handler
    def _handle_unauthorized():
        """Return JSON 401 for API paths; redirect to login for HTML paths."""
        if request.path.startswith("/api/"):
            return jsonify(error={"code": 401, "message": "Authentication required."}), 401
        flash("Please sign in to continue.", "info")
        return redirect(url_for("auth.login", next=request.full_path))

    # ── Models ──────────────────────────────────────────
    # Base models are imported via app.models. Feature models (pulse, maps,
    # notifications) are imported explicitly here so they register with
    # SQLAlchemy's metadata. Note: app.models.__init__ deliberately does NOT
    # import feature models — doing so causes a circular import when a
    # feature module is loaded standalone (e.g. by a test).
    from app import models  # noqa: F401
    from app.pulse import models as _pulse_models  # noqa: F401
    from app.maps import models as _maps_models  # noqa: F401
    from app.notifications import models as _notifications_models  # noqa: F401

    # ── Blueprints ──────────────────────────────────────
    from app.auth.routes import bp as auth_bp
    from app.users.routes import bp as users_bp
    from app.universities.routes import bp as unis_bp
    from app.web.home import bp as home_bp
    from app.pwa.routes import bp as pwa_bp
    from app.admin.routes import bp as admin_bp
    from app.pulse.routes import bp as pulse_bp
    from app.maps.routes import bp as maps_bp
    from app.notifications.routes import bp as notifications_bp
    from app.notifications.routes import page_bp as notifications_page_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(unis_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(pwa_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(pulse_bp)
    app.register_blueprint(maps_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(notifications_page_bp)

    # ── Error handlers ──────────────────────────────────
    from app.core import errors
    errors.register(app)

    # ── Security headers ────────────────────────────────
    from app.core.security_headers import register_headers
    register_headers(app)

    # ── Shell context ───────────────────────────────────
    @app.context_processor
    def inject_brand():
        return {
            "BRAND": {
                "name": "Campus OS",
                "tagline": "Your campus. One place.",
            }
        }

    @app.context_processor
    def inject_mapbox():
        return {"MAPBOX_TOKEN": app.config.get("MAPBOX_TOKEN", "")}

    # ── Health checks ───────────────────────────────────
    @app.get("/healthz")
    def healthz():
        """Liveness — no dependencies. Used by Render's health check."""
        return {"status": "ok"}, 200

    @app.get("/readyz")
    def readyz():
        """Readiness — verifies DB connectivity."""
        try:
            db.session.execute(text("SELECT 1"))
            return {"status": "ready", "db": "ok"}, 200
        except Exception:
            app.logger.exception("Readiness check failed")
            return {"status": "not_ready", "db": "error"}, 503

    @app.get("/healthz/deps")
    def healthz_deps():
        """Dependency detail. No secrets, no versions, no connection strings."""
        result = {"db": "ok", "redis": "unknown"}

        try:
            db.session.execute(text("SELECT 1"))
        except Exception:
            result["db"] = "error"

        redis_url = app.config.get("REDIS_URL")
        if redis_url:
            try:
                import redis as _redis
                client = _redis.from_url(redis_url, socket_timeout=2)
                client.ping()
                result["redis"] = "ok"
            except Exception:
                result["redis"] = "error"
        else:
            result["redis"] = "not_configured"

        status_code = 200 if result["db"] == "ok" else 503
        return jsonify(result), status_code

    return app