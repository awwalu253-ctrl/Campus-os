import json

def test_manifest(client):
    r = client.get("/manifest.webmanifest")
    assert r.status_code == 200
    data = json.loads(r.data)
    assert data["name"] == "Campus OS"
    assert data["display"] == "standalone"
    assert data["theme_color"] == "#17233F"


def test_service_worker_served_at_root(client):
    r = client.get("/service-worker.js")
    assert r.status_code == 200
    assert "Service-Worker-Allowed" in r.headers
    assert r.headers["Service-Worker-Allowed"] == "/"