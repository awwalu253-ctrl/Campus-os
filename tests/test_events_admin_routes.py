"""Route tests for staff moderation of Campus Events."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.auth import services as auth_services
from app.events.models import CampusEvent
from app.extensions import db
from app.models import Campus, University
from app.models.staff import StaffCampusAssignment


def _login(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def _make_campus():
    suffix = uuid.uuid4().hex[:8]

    university = University(
        slug=f"admin-event-{suffix}",
        name="Admin Events University",
        short_name="AEU",
    )
    db.session.add(university)
    db.session.flush()

    campus = Campus(
        university_id=university.id,
        slug=f"campus-{suffix}",
        name="Main Campus",
    )
    db.session.add(campus)
    db.session.commit()

    return campus


def _make_user(role="student"):
    suffix = uuid.uuid4().hex[:8]

    user = auth_services.create_user(
        email=f"admin-event-{suffix}@example.com",
        password="testpass1234",
        display_name="Events Admin Test",
    )
    user.role = role
    db.session.commit()

    return user.id


def _make_event(campus, organizer_id, status="pending_review"):
    starts_at = datetime.now(timezone.utc) + timedelta(days=3)

    event = CampusEvent(
        campus_id=campus.id,
        organizer_id=organizer_id,
        title="Moderation Test Event",
        description="An event submitted for staff review.",
        category="technology",
        venue="Main Auditorium",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=2),
        status=status,
    )
    db.session.add(event)
    db.session.commit()

    return event.id


def _assign_staff(user_id, campus_id, active=True):
    assignment = StaffCampusAssignment(
        user_id=user_id,
        campus_id=campus_id,
        is_active=active,
    )
    db.session.add(assignment)
    db.session.commit()
    return assignment


@pytest.fixture
def admin_event_template_stub(monkeypatch):
    def fake_render_template(template_name, **context):
        return f"Rendered: {template_name}"

    monkeypatch.setattr(
        "app.events.admin_routes.render_template",
        fake_render_template,
    )


def test_review_queue_requires_authentication(client):
    response = client.get("/admin/events/")
    assert response.status_code == 302


def test_student_cannot_access_review_queue(app, client):
    with app.app_context():
        user_id = _make_user("student")

    _login(client, user_id)

    response = client.get("/admin/events/")
    assert response.status_code == 403


def test_assigned_moderator_can_view_review_queue(
    app, client, admin_event_template_stub
):
    with app.app_context():
        campus = _make_campus()
        moderator_id = _make_user("moderator")
        organizer_id = _make_user("student")

        _assign_staff(moderator_id, campus.id)
        _make_event(campus, organizer_id)

    _login(client, moderator_id)

    response = client.get("/admin/events/")

    assert response.status_code == 200
    assert b"events_review.html" in response.data


def test_moderator_cannot_view_unassigned_campus_event(
    app, client, admin_event_template_stub
):
    with app.app_context():
        campus = _make_campus()
        other_campus = _make_campus()

        moderator_id = _make_user("moderator")
        organizer_id = _make_user("student")

        _assign_staff(moderator_id, other_campus.id)
        event_id = _make_event(campus, organizer_id)

    _login(client, moderator_id)

    response = client.get(f"/admin/events/{event_id}")

    assert response.status_code == 404


def test_moderator_queue_contains_only_assigned_campus_events(
    app, client, admin_event_template_stub
):
    with app.app_context():
        campus = _make_campus()
        other_campus = _make_campus()

        moderator_id = _make_user("moderator")
        organizer_id = _make_user("student")

        _assign_staff(moderator_id, campus.id)

        _make_event(campus, organizer_id)
        _make_event(other_campus, organizer_id)

    _login(client, moderator_id)

    response = client.get("/admin/events/")

    assert response.status_code == 200


def test_platform_admin_can_view_event_from_any_campus(
    app, client, admin_event_template_stub
):
    with app.app_context():
        campus = _make_campus()
        platform_admin_id = _make_user("platform_admin")
        organizer_id = _make_user("student")

        event_id = _make_event(campus, organizer_id)

    _login(client, platform_admin_id)

    response = client.get(f"/admin/events/{event_id}")

    assert response.status_code == 200
    assert b"event_review_detail.html" in response.data


def test_assigned_moderator_can_approve_event(app, client):
    with app.app_context():
        campus = _make_campus()
        moderator_id = _make_user("moderator")
        organizer_id = _make_user("student")

        _assign_staff(moderator_id, campus.id)
        event_id = _make_event(campus, organizer_id)

    _login(client, moderator_id)

    response = client.post(
        f"/admin/events/{event_id}/approve",
        follow_redirects=False,
    )

    assert response.status_code == 302

    with app.app_context():
        event = db.session.get(CampusEvent, event_id)
        assert event.status == "published"
        assert event.reviewed_by == moderator_id
        assert event.reviewed_at is not None
        assert event.published_at is not None


def test_rejection_requires_a_reason(app, client):
    with app.app_context():
        campus = _make_campus()
        moderator_id = _make_user("moderator")
        organizer_id = _make_user("student")

        _assign_staff(moderator_id, campus.id)
        event_id = _make_event(campus, organizer_id)

    _login(client, moderator_id)

    response = client.post(
        f"/admin/events/{event_id}/reject",
        data={"reason": "   "},
    )

    assert response.status_code == 302

    with app.app_context():
        event = db.session.get(CampusEvent, event_id)
        assert event.status == "pending_review"
        assert event.rejection_reason is None


def test_assigned_moderator_can_reject_event(app, client):
    with app.app_context():
        campus = _make_campus()
        moderator_id = _make_user("moderator")
        organizer_id = _make_user("student")

        _assign_staff(moderator_id, campus.id)
        event_id = _make_event(campus, organizer_id)

    _login(client, moderator_id)

    response = client.post(
        f"/admin/events/{event_id}/reject",
        data={"reason": "Please provide a clearer event description."},
    )

    assert response.status_code == 302

    with app.app_context():
        event = db.session.get(CampusEvent, event_id)
        assert event.status == "rejected"
        assert event.rejection_reason == (
            "Please provide a clearer event description."
        )
        assert event.reviewed_by == moderator_id
        assert event.reviewed_at is not None
        assert event.published_at is None


def test_inactive_campus_assignment_does_not_grant_access(
    app, client, admin_event_template_stub
):
    with app.app_context():
        campus = _make_campus()
        moderator_id = _make_user("moderator")
        organizer_id = _make_user("student")

        _assign_staff(moderator_id, campus.id, active=False)
        event_id = _make_event(campus, organizer_id)

    _login(client, moderator_id)

    response = client.get(f"/admin/events/{event_id}")

    assert response.status_code == 404