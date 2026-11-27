"""Batch 1 regression tests — Pulse access control & interaction integrity."""
import uuid

import pytest

from app.extensions import db
from app.models import Campus, University, StudentProfile, User
from app.pulse.models import CampusReport
from app.pulse import categories as pulse_categories
from app.pulse import services
from app.auth import services as auth_services


# ── Helpers ────────────────────────────────────────────────
def _make_campus(app, *, role_suffix=None):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(
            slug=f"uni-{suffix}", name=f"Uni {suffix}",
            short_name="TU", state="Test",
        )
        db.session.add(uni); db.session.flush()
        campus = Campus(
            university_id=uni.id, slug=f"main-{suffix}",
            name=f"Campus {suffix}", lat=8.4920, lng=4.6736,
        )
        db.session.add(campus); db.session.commit()
        return {"campus_id": campus.id, "university_id": uni.id}


def _make_user(app, campus_id, university_id, *, role="student"):
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        user = auth_services.create_user(
            email=f"ac-{suffix}@example.com",
            password="testpass1234",
            display_name="Access Tester",
        )
        db.session.flush()
        profile = StudentProfile.query.filter_by(user_id=user.id).first()
        if profile is None:
            profile = StudentProfile(user_id=user.id)
            db.session.add(profile)
        profile.campus_id = campus_id
        profile.university_id = university_id
        if role != "student":
            user.role = role
        db.session.commit()
        return user.id


def _make_report(app, campus_id, reporter_id, *, category=None,
                 moderation_status="visible", status="active",
                 hours_until_expiry=2):
    from datetime import datetime, timedelta, timezone
    with app.app_context():
        cat = category or next(iter(pulse_categories.CATEGORIES))
        r = CampusReport(
            campus_id=campus_id,
            category=cat,
            description="test",
            reported_by=reporter_id,
            status=status,
            moderation_status=moderation_status,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=hours_until_expiry),
        )
        db.session.add(r); db.session.commit()
        return r.id


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = user_id
        sess["_fresh"] = True


# ── 1. Same-campus detail access ──────────────────────────
def test_same_campus_report_detail_accessible(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other)
        _login(client, u)
        rv = client.get(f"/pulse/report/{r}")
        assert rv.status_code == 200


# ── 2. Cross-campus detail access ─────────────────────────
def test_cross_campus_report_detail_404(app, client):
    with app.app_context():
        a = _make_campus(app)
        b = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, b["campus_id"], b["university_id"])
        r = _make_report(app, b["campus_id"], other)
        _login(client, u)
        rv = client.get(f"/pulse/report/{r}")
        assert rv.status_code == 404


# ── 3. Hidden report — non-staff 404, staff 200 ───────────
def test_hidden_report_detail_404_for_non_staff(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other, moderation_status="hidden")
        _login(client, u)
        rv = client.get(f"/pulse/report/{r}")
        assert rv.status_code == 404


def test_hidden_report_detail_200_for_staff(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"], role="moderator")
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other, moderation_status="hidden")
        _login(client, u)
        rv = client.get(f"/pulse/report/{r}")
        assert rv.status_code == 200


# ── 4. Removed report 404 (any user) ──────────────────────
def test_removed_report_detail_404(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other,
                         status="removed", moderation_status="removed")
        _login(client, u)
        rv = client.get(f"/pulse/report/{r}")
        assert rv.status_code == 404


# ── 5. Same-campus confirm/disagree/flag accepted ─────────
def test_same_campus_confirm_accepted(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other)
        _login(client, u)
        rv = client.post(f"/pulse/report/{r}/confirm", follow_redirects=False)
        assert rv.status_code in (302, 303)
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.confirmation_count == 1


def test_same_campus_disagree_accepted(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other)
        _login(client, u)
        rv = client.post(f"/pulse/report/{r}/disagree", follow_redirects=False)
        assert rv.status_code in (302, 303)
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.disagreement_count == 1


def test_same_campus_flag_accepted(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other)
        _login(client, u)
        rv = client.post(f"/pulse/report/{r}/flag",
                         data={"reason": "test"}, follow_redirects=False)
        assert rv.status_code in (302, 303)
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.flag_count == 1


# ── 6. Cross-campus confirm/disagree/flag → 404 ──────────
def test_cross_campus_confirm_404(app, client):
    with app.app_context():
        a = _make_campus(app)
        b = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, b["campus_id"], b["university_id"])
        r = _make_report(app, b["campus_id"], other)
        _login(client, u)
        rv = client.post(f"/pulse/report/{r}/confirm", follow_redirects=False)
        assert rv.status_code == 404
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.confirmation_count == 0


def test_cross_campus_disagree_404(app, client):
    with app.app_context():
        a = _make_campus(app)
        b = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, b["campus_id"], b["university_id"])
        r = _make_report(app, b["campus_id"], other)
        _login(client, u)
        rv = client.post(f"/pulse/report/{r}/disagree", follow_redirects=False)
        assert rv.status_code == 404
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.disagreement_count == 0


def test_cross_campus_flag_404(app, client):
    with app.app_context():
        a = _make_campus(app)
        b = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, b["campus_id"], b["university_id"])
        r = _make_report(app, b["campus_id"], other)
        _login(client, u)
        rv = client.post(f"/pulse/report/{r}/flag",
                         data={"reason": "test"}, follow_redirects=False)
        assert rv.status_code == 404
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.flag_count == 0


# ── 7. Confirm/disagree on hidden report → rejected ──────
def test_confirm_hidden_report_rejected(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other, moderation_status="hidden")
        _login(client, u)
        # Non-staff: 404 at route level (hidden blocked)
        rv = client.post(f"/pulse/report/{r}/confirm", follow_redirects=False)
        assert rv.status_code == 404
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.confirmation_count == 0


def test_disagree_hidden_report_rejected(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other, moderation_status="hidden")
        _login(client, u)
        rv = client.post(f"/pulse/report/{r}/disagree", follow_redirects=False)
        assert rv.status_code == 404
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.disagreement_count == 0


# ── 8. Hidden report cannot be flagged (staff also blocked by service) ──
def test_flag_hidden_report_rejected(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"], role="moderator")
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other, moderation_status="hidden")
        _login(client, u)
        # Route allows staff to reach the report (200 at detail level),
        # but flagging is refused by the service -> flash + 302.
        rv = client.post(f"/pulse/report/{r}/flag",
                         data={"reason": "test"}, follow_redirects=False)
        assert rv.status_code in (302, 303)
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.flag_count == 0


# ── 9. Flag expired/removed report rejected (service-level via staff) ──
def test_flag_expired_report_rejected(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other,
                         status="expired", hours_until_expiry=-1)
        _login(client, u)
        rv = client.post(f"/pulse/report/{r}/flag",
                         data={"reason": "test"}, follow_redirects=False)
        # Route allows because status != "removed" and visible, but service
        # rejects. Assert flash + redirect, no flag_count increase.
        assert rv.status_code in (302, 303)
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.flag_count == 0


def test_flag_removed_report_rejected(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other,
                         status="removed", moderation_status="removed")
        _login(client, u)
        rv = client.post(f"/pulse/report/{r}/flag",
                         data={"reason": "test"}, follow_redirects=False)
        assert rv.status_code == 404
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.flag_count == 0


# ── 10. Reporter cannot confirm/disagree own report ──────
def test_reporter_cannot_confirm_own(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], u)
        _login(client, u)
        rv = client.post(f"/pulse/report/{r}/confirm", follow_redirects=True)
        assert rv.status_code == 200
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.confirmation_count == 0


def test_reporter_cannot_disagree_own(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], u)
        _login(client, u)
        rv = client.post(f"/pulse/report/{r}/disagree", follow_redirects=True)
        assert rv.status_code == 200
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.disagreement_count == 0


# ── 11. Confirm↔Disagree flip behavior preserved ─────────
def test_confirm_to_disagree_flip_works(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other)
        _login(client, u)
        client.post(f"/pulse/report/{r}/confirm", follow_redirects=False)
        client.post(f"/pulse/report/{r}/disagree", follow_redirects=False)
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.confirmation_count == 0
            assert rep.disagreement_count == 1


# ── 12. Duplicate protections intact ─────────────────────
def test_duplicate_confirm_raises(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other)
        _login(client, u)
        client.post(f"/pulse/report/{r}/confirm", follow_redirects=False)
        client.post(f"/pulse/report/{r}/confirm", follow_redirects=False)
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.confirmation_count == 1


def test_duplicate_flag_raises(app, client):
    with app.app_context():
        a = _make_campus(app)
        u = _make_user(app, a["campus_id"], a["university_id"])
        other = _make_user(app, a["campus_id"], a["university_id"])
        r = _make_report(app, a["campus_id"], other)
        _login(client, u)
        client.post(f"/pulse/report/{r}/flag",
                    data={"reason": "test"}, follow_redirects=False)
        client.post(f"/pulse/report/{r}/flag",
                    data={"reason": "test"}, follow_redirects=False)
        with app.app_context():
            rep = db.session.get(CampusReport, r)
            assert rep.flag_count == 1