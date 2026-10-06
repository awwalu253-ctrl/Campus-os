def register_headers(app):
    is_production = (app.config.get("ENV") == "production")

    # Content Security Policy — allows Mapbox, Google Fonts, and self.
    # Blocks inline scripts except where the map template uses them
    # (that template passes a JSON config via a <script> block).
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://api.mapbox.com; "
        "style-src 'self' 'unsafe-inline' https://api.mapbox.com https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com data:; "
        "img-src 'self' data: blob: https://api.mapbox.com https://*.tiles.mapbox.com; "
        "connect-src 'self' https://api.mapbox.com https://events.mapbox.com; "
        "worker-src 'self' blob:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "object-src 'none'"
    )

    @app.after_request
    def _headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(self), camera=(), microphone=()",
        )
        resp.headers.setdefault("Content-Security-Policy", csp)

        if is_production:
            resp.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return resp