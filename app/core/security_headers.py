def register_headers(app):
    @app.after_request
    def _headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault(
            "Permissions-Policy",
            "geolocation=(self), camera=(), microphone=()",
        )
        # CSP tightened in later phases when Mapbox is added.
        if app.config.get("ENV") == "production":
            resp.headers.setdefault("Strict-Transport-Security",
                                    "max-age=31536000; includeSubDomains")
        return resp