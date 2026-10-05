from flask import render_template, request, jsonify
from werkzeug.exceptions import HTTPException


def _wants_json() -> bool:
    if request.path.startswith("/api/"):
        return True
    return request.accept_mimetypes.best == "application/json"


def register(app):
    @app.errorhandler(403)
    def _403(e):    return _render(403, "You don't have access to that.")
    @app.errorhandler(404)
    def _404(e):    return _render(404, "We couldn't find that page.")
    @app.errorhandler(429)
    def _429(e):    return _render(429, "Too many requests. Slow down a moment.")
    @app.errorhandler(500)
    def _500(e):    return _render(500, "Something went wrong on our end.")
    @app.errorhandler(HTTPException)
    def _http(e):   return _render(e.code or 500, e.description)

    def _render(code: int, message: str):
        if _wants_json():
            return jsonify(error={"code": code, "message": message}), code
        return render_template(f"errors/{code}.html", code=code, message=message), code