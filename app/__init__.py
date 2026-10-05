from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template

from app.config import get_config
from app.extensions import db, migrate, login_manager, csrf, limiter


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=False)

    # ── Config ──────────────────────────────────────────
    cfg = get_config(config_name)
    app.config.from_object(cfg)

    # ── Extensions ──────────────────────────────────────
    db.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)
    limiter.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "info"

    # ── Models (import side effect: registers metadata) ─
    # Do NOT import feature models directly here. Everything routes
    # through app.models.__init__, which is the single registration
    # surface for SQLAlchemy metadata.
    from app import models  # noqa: F401

    # ── Blueprints ──────────────────────────────────────
    from app.auth.routes import bp as auth_bp
    from app.users.routes import bp as users_bp
    from app.universities.routes import bp as unis_bp
    from app.web.home import bp as home_bp
    from app.pwa.routes import bp as pwa_bp
    from app.admin.routes import bp as admin_bp
    from app.pulse.routes import bp as pulse_bp
    from app.maps.routes import bp as maps_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(unis_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(pwa_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(pulse_bp)
    app.register_blueprint(maps_bp)

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

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}, 200

    return app