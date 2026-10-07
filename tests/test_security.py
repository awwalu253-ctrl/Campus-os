def test_security_headers_present(client):
    r = client.get("/healthz")
    h = r.headers
    assert h.get("X-Content-Type-Options") == "nosniff"
    assert h.get("X-Frame-Options") == "DENY"
    assert "strict-origin-when-cross-origin" in h.get("Referrer-Policy", "")
    assert "geolocation=(self)" in h.get("Permissions-Policy", "")
    assert "Content-Security-Policy" in h


def test_csp_allows_mapbox(client):
    r = client.get("/healthz")
    csp = r.headers.get("Content-Security-Policy", "")
    assert "https://api.mapbox.com" in csp
    assert "https://*.tiles.mapbox.com" in csp
    assert "blob:" in csp
    assert "frame-ancestors 'none'" in csp
    assert "object-src 'none'" in csp


def test_csp_allows_google_fonts(client):
    r = client.get("/healthz")
    csp = r.headers.get("Content-Security-Policy", "")
    assert "https://fonts.googleapis.com" in csp
    assert "https://fonts.gstatic.com" in csp