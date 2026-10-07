def test_register_and_login(client):
    r = client.post("/auth/register", data={
        "display_name": "Awwalu Test",
        "email": "awwalu@example.com",
        "phone": "",
        "password": "supersecret123",
        "confirm": "supersecret123",
        "accept_terms": "y",
    }, follow_redirects=False)
    assert r.status_code in (302, 303)
    # Registering logs the user in and redirects to onboarding
    assert "/onboarding" in r.headers["Location"]

    client.post("/auth/logout", follow_redirects=True)
    r = client.post("/auth/login", data={
        "email": "awwalu@example.com",
        "password": "supersecret123",
    }, follow_redirects=False)
    assert r.status_code in (302, 303)


def test_login_wrong_password(client):
    r = client.post("/auth/login", data={
        "email": "awwalu@example.com",
        "password": "nope",
    }, follow_redirects=False)
    print("\n--- DIAGNOSTIC ---")
    print("STATUS:", r.status_code)
    print("BODY:", r.data[:400])
    print("--- END ---")
    assert b"Invalid" in r.data