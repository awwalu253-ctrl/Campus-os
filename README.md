# Campus OS

Your campus. One place.

## Phase 1 — Foundation
Working: auth, users, university hierarchy, app shell, PWA install + splash,
admin CLI, dev seed.

Not yet: Pulse, Map, Tasks, Notifications (later phases).

## Local setup
1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` — set `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`
4. Postgres (with PostGIS preferred):
   `createdb campusos && createdb campusos_test`
5. `flask db init && flask db migrate -m "initial" && flask db upgrade`
6. `python -m scripts.seed_dev`
7. `python -m scripts.create_admin you@example.com "Your Name"`
8. `python run.py`

## Tests
`pytest -q`

## Deploy (Render)
`render.yaml` provisions web + Postgres + Redis. Set `SECRET_KEY` and
optional third-party env vars in the Render dashboard.

## Runbook
- `flask db upgrade` on every deploy
- Health check: `GET /healthz`
- PWA: open the site, use "Add to Home Screen"