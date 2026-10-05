from flask import Blueprint, send_from_directory, current_app, make_response

bp = Blueprint("pwa", __name__)


@bp.get("/service-worker.js")
def service_worker():
    resp = make_response(send_from_directory(
        current_app.static_folder, "service-worker.js", mimetype="application/javascript"
    ))
    # SW must be served from / to control the whole scope
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@bp.get("/manifest.webmanifest")
def manifest():
    return send_from_directory(
        current_app.static_folder, "manifest.webmanifest",
        mimetype="application/manifest+json",
    )


@bp.get("/offline")
def offline():
    from flask import render_template
    return render_template("offline.html")