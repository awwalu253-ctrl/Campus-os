def test_healthz_returns_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json == {"status": "ok"}


def test_readyz_checks_db(client):
    r = client.get("/readyz")
    assert r.status_code == 200
    assert r.json["status"] == "ready"
    assert r.json["db"] == "ok"


def test_healthz_deps_returns_db_status(client):
    r = client.get("/healthz/deps")
    assert r.status_code == 200
    body = r.json
    assert "db" in body
    assert "redis" in body
    assert body["db"] == "ok"

    # No secrets or connection strings in the response.
    blob = str(body).lower()
    for forbidden in ("password", "secret", "postgres://", "redis://"):
        assert forbidden not in blob