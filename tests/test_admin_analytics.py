"""Tests for the admin Analytics page and its SVG sparkline helpers.

Covers /admin/analytics plus the pure helper functions used by it:

  - _sparkline_svg  — must handle empty, single-point, all-zero, and
                      varying-value inputs without crashing and produce
                      well-formed SVG in each case.
  - _fill_daily_series — must densify sparse (date, count) rows into a
                      zero-filled list covering the full range.

The helpers are unit-tested directly (no DB, no HTTP) so a broken
sparkline fails visibly and specifically.
"""
import uuid
from datetime import date

import pytest

from app.admin.routes import _fill_daily_series, _sparkline_svg
from app.core.security import hash_password
from app.extensions import db
from app.models import User


@pytest.fixture
def admin(app):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        u = User(
            email=f"admin-{suffix}@example.com",
            display_name="Admin",
            password_hash=hash_password("testpass1234"),
            role="platform_admin",
            status="active",
        )
        db.session.add(u)
        db.session.commit()
        return u.id


def _login(client, user_id):
    with client.session_transaction() as s:
        s["_user_id"] = user_id
        s["_fresh"] = True


# ── HTTP-level tests ──────────────────────────────────────
def test_admin_analytics_requires_auth(client):
    r = client.get("/admin/analytics")
    assert r.status_code == 302


def test_admin_analytics_requires_admin(app, client):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        u = User(
            email=f"student-{suffix}@example.com",
            display_name="Student",
            password_hash=hash_password("testpass1234"),
            role="student",
            status="active",
        )
        db.session.add(u)
        db.session.commit()
        sid = u.id
    _login(client, sid)
    r = client.get("/admin/analytics")
    assert r.status_code == 403


def test_admin_analytics_renders_for_admin(app, client, admin):
    _login(client, admin)
    r = client.get("/admin/analytics")
    assert r.status_code == 200

    body = r.data
    # The four top-level section headers.
    for label in (
        b"In this range",
        b"Per day",
        b"Breakdowns",
        b"Moderation throughput",
    ):
        assert label in body, f"missing section label: {label}"

    # The headline cards.
    for label in (
        b"New users",
        b"New reports",
        b"New locations",
        b"Notifications",
        b"Suggestion approvals",
        b"Admin actions",
    ):
        assert label in body, f"missing headline card: {label}"


def test_admin_analytics_accepts_date_range(app, client, admin):
    _login(client, admin)
    r = client.get(
        "/admin/analytics?date_from=2026-01-01&date_to=2026-01-31"
    )
    assert r.status_code == 200

    body = r.data
    # The raw inputs round-trip into the page.
    assert b"2026-01-01" in body
    assert b"2026-01-31" in body
    # The section title reflects the resolved range.
    assert b"2026-01-01" in body and b"2026-01-31" in body


def test_admin_analytics_handles_reversed_range(app, client, admin):
    _login(client, admin)
    # from > to → reset to default 30-day window with a visible notice.
    r = client.get(
        "/admin/analytics?date_from=2026-01-31&date_to=2026-01-01"
    )
    assert r.status_code == 200
    # The reset notice should appear somewhere in the rendered HTML.
    assert b"Start date was after end date" in r.data


def test_admin_analytics_handles_malformed_dates(app, client, admin):
    _login(client, admin)
    r = client.get(
        "/admin/analytics?date_from=not-a-date&date_to=also-not-a-date"
    )
    # Should render cleanly against the default range, not 500.
    assert r.status_code == 200
    assert b"In this range" in r.data


# ── Helper unit tests ─────────────────────────────────────
def test_sparkline_svg_empty_input():
    """Empty series returns a bare SVG with no rendering primitives."""
    svg = _sparkline_svg([], aria_label="Empty series")
    assert svg.startswith("<svg")
    assert svg.endswith("</svg>")
    # No line, no circle, no polyline in the empty case.
    assert "<polyline" not in svg
    assert "<circle" not in svg
    assert "<line" not in svg
    # Aria label present.
    assert 'aria-label="Empty series"' in svg


def test_sparkline_svg_single_point():
    """Single-element series returns a circle at the centre."""
    svg = _sparkline_svg([5], aria_label="Single")
    assert "<circle" in svg
    # No polyline for a one-point series.
    assert "<polyline" not in svg


def test_sparkline_svg_all_zeros():
    """All-zero series returns a horizontal line at mid-height."""
    svg = _sparkline_svg([0, 0, 0, 0], aria_label="Zeros")
    assert "<line" in svg
    # No polyline when every value is zero.
    assert "<polyline" not in svg


def test_sparkline_svg_varying_values():
    """Varying series returns a polyline with one coordinate per value."""
    svg = _sparkline_svg([1, 3, 2, 5, 4], aria_label="Varying")
    assert "<polyline" in svg
    # The polyline has one "x,y" pair per input value.
    start = svg.index('points="') + len('points="')
    end = svg.index('"', start)
    coords = svg[start:end].split()
    assert len(coords) == 5


def test_fill_daily_series_fills_gaps():
    """Sparse query rows densify to a full calendar series."""
    rows = [(date(2026, 10, 2), 3)]  # only one day has data
    filled = _fill_daily_series(
        rows,
        from_date=date(2026, 10, 1),
        to_date=date(2026, 10, 5),
    )
    assert filled == [0, 3, 0, 0, 0]