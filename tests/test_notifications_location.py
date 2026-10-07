"""Tests for location-suggestion notification integration (Stage 4).

Covers three areas the inline Stage 4 verification did not:

  1. Cross-user isolation — one user cannot read or mark another user's
     notification.
  2. Atomicity — rolling back the moderation transaction rolls back the
     notification too.
  3. Regression — the existing moderation workflow (status transitions,
     Location creation) is unchanged.

Every test uses the app fixture from conftest.py, which creates a fresh
schema and drops it after each test. Committed rows do not leak between
tests.
"""
import uuid

import pytest

from app.auth import services as auth_services
from app.extensions import db
from app.maps import services as map_services
from app.maps.models import Location, LocationSuggestion
from app.models import Campus, University
from app.notifications import services as notif_services
from app.notifications.models import Notification


# ── Fixtures ──────────────────────────────────────────────
@pytest.fixture
def seeded(app):
    """Create a university, a campus, and three distinct users."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]

        uni = University(
            slug=f"notif-loc-uni-{suffix}",
            name=f"Notif Loc Uni {suffix}",
            short_name=f"NLU{suffix}",
        )
        db.session.add(uni)
        db.session.flush()

        campus = Campus(
            university_id=uni.id,
            slug="main",
            name="Main Campus",
        )
        db.session.add(campus)
        db.session.flush()

        suggester = auth_services.create_user(
            email=f"loc-sug-{suffix}@example.com",
            password="testpass1234",
            display_name=f"Suggester {suffix}",
        )
        moderator = auth_services.create_user(
            email=f"loc-mod-{suffix}@example.com",
            password="testpass1234",
            display_name=f"Moderator {suffix}",
        )
        other = auth_services.create_user(
            email=f"loc-oth-{suffix}@example.com",
            password="testpass1234",
            display_name=f"Other {suffix}",
        )
        db.session.commit()

        return {
            "campus_id": campus.id,
            "suggester_id": suggester.id,
            "moderator_id": moderator.id,
            "other_id": other.id,
        }


def _make_suggestion(campus_id, suggester_id, name="Test Suggestion"):
    return map_services.suggest_location(
        campus_id=campus_id,
        user_id=suggester_id,
        name=name,
        category="library",
        lat=8.48,
        lng=4.67,
        description="Test description",
    )


# ═══════════════════════════════════════════════════════════
# 1. Cross-user isolation
# ═══════════════════════════════════════════════════════════
def test_isolation_suggester_can_read_own_notification(app, seeded):
    with app.app_context():
        sug = _make_suggestion(seeded["campus_id"], seeded["suggester_id"])
        db.session.commit()
        map_services.approve_suggestion(sug, moderator_id=seeded["moderator_id"])
        db.session.commit()

        notifications = notif_services.get_user_notifications(seeded["suggester_id"])
        approval = [n for n in notifications if n.type == "location_suggestion_approved"]

        assert len(approval) == 1
        assert approval[0].recipient_id == seeded["suggester_id"]


def test_isolation_other_user_cannot_list_notification(app, seeded):
    with app.app_context():
        sug = _make_suggestion(seeded["campus_id"], seeded["suggester_id"])
        db.session.commit()
        map_services.approve_suggestion(sug, moderator_id=seeded["moderator_id"])
        db.session.commit()

        other_notifications = notif_services.get_user_notifications(seeded["other_id"])
        assert other_notifications == []

        suggester_notifications = notif_services.get_user_notifications(seeded["suggester_id"])
        assert any(n.type == "location_suggestion_approved" for n in suggester_notifications)


def test_isolation_other_user_cannot_mark_read(app, seeded):
    with app.app_context():
        sug = _make_suggestion(seeded["campus_id"], seeded["suggester_id"])
        db.session.commit()
        map_services.approve_suggestion(sug, moderator_id=seeded["moderator_id"])
        db.session.commit()

        notif = Notification.query.filter_by(
            recipient_id=seeded["suggester_id"],
            type="location_suggestion_approved",
        ).one()

        result = notif_services.mark_notification_read(notif.id, seeded["other_id"])
        db.session.commit()

        assert result is False

        refreshed = db.session.get(Notification, notif.id)
        assert refreshed.read_at is None


# ═══════════════════════════════════════════════════════════
# 2. Atomicity — rollback undoes both moderation and notification
# ═══════════════════════════════════════════════════════════
def test_rollback_discards_moderation_and_notification(app, seeded):
    with app.app_context():
        sug = _make_suggestion(seeded["campus_id"], seeded["suggester_id"])
        db.session.commit()
        suggestion_id = sug.id

        map_services.approve_suggestion(sug, moderator_id=seeded["moderator_id"])
        db.session.rollback()

        refreshed = db.session.get(LocationSuggestion, suggestion_id)
        assert refreshed is not None
        assert refreshed.status == "pending"
        assert refreshed.approved_location_id is None

        notifications = Notification.query.filter_by(
            recipient_id=seeded["suggester_id"],
        ).all()
        assert notifications == []


# ═══════════════════════════════════════════════════════════
# 3. Regression — moderation workflow unchanged
# ═══════════════════════════════════════════════════════════
def test_approval_workflow_creates_location_and_notification(app, seeded):
    with app.app_context():
        sug = _make_suggestion(
            seeded["campus_id"], seeded["suggester_id"],
            name="Regression Approval Location",
        )
        db.session.commit()
        assert sug.status == "pending"

        loc = map_services.approve_suggestion(sug, moderator_id=seeded["moderator_id"])
        db.session.commit()

        assert sug.status == "approved"
        assert sug.moderated_by == seeded["moderator_id"]
        assert sug.moderated_at is not None
        assert sug.approved_location_id == loc.id

        assert loc.status == "approved"
        assert loc.source == "student"
        assert loc.created_by == seeded["suggester_id"]
        assert loc.verified_by == seeded["moderator_id"]
        assert loc.campus_id == seeded["campus_id"]

        notifications = notif_services.get_user_notifications(seeded["suggester_id"])
        approval = [n for n in notifications if n.type == "location_suggestion_approved"]
        assert len(approval) == 1
        assert approval[0].related_entity_id == sug.id
        assert approval[0].action_url == f"/map/location/{loc.id}"


def test_rejection_workflow_creates_notification_and_no_location(app, seeded):
    with app.app_context():
        before = Location.query.count()

        sug = _make_suggestion(
            seeded["campus_id"], seeded["suggester_id"],
            name="Regression Rejection Location",
        )
        db.session.commit()
        assert sug.status == "pending"

        map_services.reject_suggestion(
            sug, moderator_id=seeded["moderator_id"], note="not a real location"
        )
        db.session.commit()

        assert sug.status == "rejected"
        assert sug.moderated_by == seeded["moderator_id"]
        assert sug.moderated_at is not None
        assert sug.approved_location_id is None

        after = Location.query.count()
        assert after == before

        notifications = notif_services.get_user_notifications(seeded["suggester_id"])
        rejection = [n for n in notifications if n.type == "location_suggestion_rejected"]
        assert len(rejection) == 1
        assert rejection[0].related_entity_id == sug.id