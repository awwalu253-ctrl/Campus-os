"""Tests for the push dispatch pipeline.

The guarantee under test: creating a notification must succeed even
when push delivery fails. Push is queued only for eligible types, and
only dispatches after the DB transaction commits.
"""
import uuid
from unittest.mock import patch

import pytest

from app import create_app as _create_app
from app.auth import services as auth_services
from app.extensions import db
from app.models import Campus, University
from app.models.user import StudentProfile
from app.notifications import services as notif_services
from app.notifications import types as ntypes
from app.notifications.models import Notification, PushSubscription
from app.pulse import services as pulse_services


@pytest.fixture
def ctx(app):
    """A single user + campus for push tests."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(slug=f"pd-{suffix}", name=f"PD {suffix}", short_name=f"P{suffix}")
        db.session.add(uni)
        db.session.flush()
        campus = Campus(university_id=uni.id, slug="main", name="Main")
        db.session.add(campus)
        db.session.flush()

        u = auth_services.create_user(
            email=f"pd-{suffix}@example.com",
            password="testpass1234",
            display_name="PD",
        )
        u.profile = StudentProfile(user_id=u.id, university_id=uni.id, campus_id=campus.id)
        db.session.add(u.profile)
        db.session.commit()

        return {"user_id": u.id, "campus_id": campus.id}


def _make_subscription(user_id):
    sub = PushSubscription(
        user_id=user_id,
        endpoint=f"https://example.com/push/{uuid.uuid4().hex}",
        p256dh="A" * 87,
        auth="B" * 22,
    )
    db.session.add(sub)
    db.session.flush()
    return sub


def test_push_eligible_types_queued(app, ctx, monkeypatch):
    monkeypatch.setitem(app.config, "PUSH_ENABLED", True)
    with app.app_context():
        _make_subscription(ctx["user_id"])
        db.session.commit()

        with patch("app.notifications.push.dispatch_for_notification") as mock_dispatch:
            mock_dispatch.return_value.sent = 1
            mock_dispatch.return_value.deleted = 0
            mock_dispatch.return_value.failed = 0
            mock_dispatch.return_value.skipped = 0

            notif_services.create_notification(
                recipient_id=ctx["user_id"],
                type=ntypes.CAMPUS_SAFETY_REPORT,
                title="Test",
                dedupe_key=None,
            )
            db.session.commit()

            assert mock_dispatch.call_count == 1


def test_push_suppressed_types_not_queued(app, ctx):
    with app.app_context():
        sub = _make_subscription(ctx["user_id"])
        db.session.commit()

        with patch("app.notifications.push.dispatch_for_notification") as mock_dispatch:
            notif_services.create_notification(
                recipient_id=ctx["user_id"],
                type=ntypes.REPORT_DISAGREEMENT,
                title="Test",
                dedupe_key=None,
            )
            db.session.commit()

            assert mock_dispatch.call_count == 0


def test_milestone_type_is_queued(app, ctx, monkeypatch):
    monkeypatch.setitem(app.config, "PUSH_ENABLED", True)
    with app.app_context():
        _make_subscription(ctx["user_id"])
        db.session.commit()

        with patch("app.notifications.push.dispatch_for_notification") as mock_dispatch:
            mock_dispatch.return_value.sent = 1
            mock_dispatch.return_value.deleted = 0
            mock_dispatch.return_value.failed = 0
            mock_dispatch.return_value.skipped = 0

            notif_services.create_notification(
                recipient_id=ctx["user_id"],
                type=ntypes.REPORT_CONFIRMATION_MILESTONE,
                title="Test",
                dedupe_key=None,
            )
            db.session.commit()

            assert mock_dispatch.call_count == 1


# ── Transaction safety ────────────────────────────────────
def test_push_not_dispatched_on_rollback(app, ctx):
    """If the caller rolls back, push must not be attempted."""
    with app.app_context():
        sub = _make_subscription(ctx["user_id"])
        db.session.commit()

        with patch("app.notifications.push.dispatch_for_notification") as mock_dispatch:
            notif_services.create_notification(
                recipient_id=ctx["user_id"],
                type=ntypes.CAMPUS_SAFETY_REPORT,
                title="Rollback test",
                dedupe_key=None,
            )
            db.session.rollback()

            assert mock_dispatch.call_count == 0


def test_push_failure_does_not_rollback_notification(app, ctx):
    """A push exception must not affect the notification row."""
    with app.app_context():
        sub = _make_subscription(ctx["user_id"])
        db.session.commit()

        with patch("app.notifications.push.dispatch_for_notification") as mock_dispatch:
            mock_dispatch.side_effect = RuntimeError("simulated push crash")

            notif_services.create_notification(
                recipient_id=ctx["user_id"],
                type=ntypes.CAMPUS_SAFETY_REPORT,
                title="Push crash test",
                dedupe_key=None,
            )
            # No exception escapes; commit succeeds
            db.session.commit()

        # The notification is in the database despite push crashing
        row = Notification.query.filter_by(
            recipient_id=ctx["user_id"],
            title="Push crash test",
        ).one()
        assert row is not None


def test_safety_report_queues_push_for_recipients(app, ctx, monkeypatch):
    monkeypatch.setitem(app.config, "PUSH_ENABLED", True)
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        recipient = auth_services.create_user(
            email=f"pd-r-{suffix}@example.com",
            password="testpass1234",
            display_name="Recipient",
        )

        # Reuse reporter's university_id
        reporter_profile = StudentProfile.query.filter_by(user_id=ctx["user_id"]).one()
        recipient.profile = StudentProfile(
            user_id=recipient.id,
            university_id=reporter_profile.university_id,
            campus_id=ctx["campus_id"],
        )
        db.session.add(recipient.profile)
        db.session.commit()

        _make_subscription(recipient.id)
        db.session.commit()

        from app.models import User
        reporter = db.session.get(User, ctx["user_id"])

        with patch("app.notifications.push.dispatch_for_notification") as mock_dispatch:
            mock_dispatch.return_value.sent = 1
            mock_dispatch.return_value.deleted = 0
            mock_dispatch.return_value.failed = 0
            mock_dispatch.return_value.skipped = 0

            pulse_services.create_report(
                user=reporter,
                campus_id=ctx["campus_id"],
                category="suspicious_activity",
                description="Push test",
            )
            db.session.commit()

            assert mock_dispatch.call_count == 1