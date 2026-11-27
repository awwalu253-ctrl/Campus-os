"""Route tests for the student-facing Campus Events pages."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.auth import services as auth_services
from app.events.models import CampusEvent, EventRSVP
from app.events.routes import event_wat
from app.extensions import db
from app.models import Campus, StudentProfile, University


def _login(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = user_id
        session["_fresh"] = True


def _make_campus():
    suffix = uuid.uuid4().hex[:8]

    university = University(
        slug=f"route-test-{suffix}",
        name="Events Route University",
        short_name="ERU",
    )
    db.session.add(university)
    db.session.flush()

    campus = Campus(
        university_id=university.id,
        slug=f"main-{suffix}",
        name="Main Campus",
    )
    db.session.add(campus)
    db.session.commit()

    return campus


def _make_user(*, role="student", campus=None):
    suffix = uuid.uuid4().hex[:8]

    user = auth_services.create_user(
        email=f"route-{suffix}@example.com",
        password="testpass1234",
        display_name="Events Route Test",
    )
    user.role = role

    if campus is not None:
        user.profile = StudentProfile(
            university_id=campus.university_id,
            campus_id=campus.id,
        )

    db.session.commit()
    return user.id


def _make_event(*, campus, organizer_id, status="draft", title="Route Test Event"):
    starts_at = datetime.now(timezone.utc) + timedelta(days=3)

    event = CampusEvent(
        campus_id=campus.id,
        organizer_id=organizer_id,
        title=title,
        description="A test event description.",
        category="technology",
        venue="Main Auditorium",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(hours=2),
        status=status,
    )
    db.session.add(event)
    db.session.commit()
    return event.id


def _valid_form_data(**overrides):
    starts_at = datetime.now(timezone.utc) + timedelta(days=3)

    # The form accepts Nigerian local time (UTC+1).
    local_start = starts_at.astimezone(
        timezone(timedelta(hours=1))
    ).replace(tzinfo=None)

    local_end = local_start + timedelta(hours=2)

    data = {
        "title": "Student Tech Meetup",
        "description": "A meetup for students interested in technology.",
        "category": "technology",
        "venue": "Main Auditorium",
        "starts_at": local_start.strftime("%Y-%m-%dT%H:%M"),
        "ends_at": local_end.strftime("%Y-%m-%dT%H:%M"),
        "capacity": "",
    }
    data.update(overrides)
    return data


@pytest.fixture
def event_template_stub(monkeypatch):
    """Avoid depending on Phase 5 templates in route tests."""
    def fake_render_template(template_name, **context):
        return f"Rendered: {template_name}"

    monkeypatch.setattr(
        "app.events.routes.render_template",
        fake_render_template,
    )


def test_events_index_requires_authentication(client):
    response = client.get("/events/")
    assert response.status_code == 302


def test_events_index_rejects_non_student(app, client):
    with app.app_context():
        user_id = _make_user(role="moderator")

    _login(client, user_id)

    response = client.get("/events/")
    assert response.status_code == 403


def test_events_index_redirects_student_without_campus(app, client):
    with app.app_context():
        user_id = _make_user()

    _login(client, user_id)

    response = client.get("/events/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/profile")


def test_events_index_renders_for_student(app, client, event_template_stub):
    with app.app_context():
        campus = _make_campus()
        user_id = _make_user(campus=campus)

    _login(client, user_id)

    response = client.get("/events/")
    assert response.status_code == 200
    assert b"pages/events/index.html" in response.data


def test_event_create_persists_draft(app, client, event_template_stub):
    with app.app_context():
        campus = _make_campus()
        user_id = _make_user(campus=campus)

    _login(client, user_id)

    response = client.post(
        "/events/new",
        data=_valid_form_data(),
    )

    assert response.status_code == 302
    assert "/events/" in response.headers["Location"]
    assert response.headers["Location"].endswith("/edit")

    with app.app_context():
        event = CampusEvent.query.filter_by(
            title="Student Tech Meetup"
        ).one()

        assert event.organizer_id == user_id
        assert event.campus_id is not None
        assert event.status == "draft"
        assert event.capacity is None


def test_event_create_rejects_invalid_category(app, client, event_template_stub):
    with app.app_context():
        campus = _make_campus()
        user_id = _make_user(campus=campus)

    _login(client, user_id)

    response = client.post(
        "/events/new",
        data=_valid_form_data(category="not-a-category"),
    )

    assert response.status_code == 200

    with app.app_context():
        assert CampusEvent.query.count() == 0


def test_event_owner_can_open_edit_page(app, client, event_template_stub):
    with app.app_context():
        campus = _make_campus()
        user_id = _make_user(campus=campus)
        event_id = _make_event(
            campus=campus,
            organizer_id=user_id,
        )

    _login(client, user_id)

    response = client.get(f"/events/{event_id}/edit")
    assert response.status_code == 200
    assert b"pages/events/edit.html" in response.data


def test_student_cannot_edit_another_students_event(app, client):
    with app.app_context():
        campus = _make_campus()
        owner_id = _make_user(campus=campus)
        other_id = _make_user(campus=campus)
        event_id = _make_event(
            campus=campus,
            organizer_id=owner_id,
        )

    _login(client, other_id)

    response = client.get(f"/events/{event_id}/edit")
    assert response.status_code == 404

    response = client.post(
        f"/events/{event_id}/edit",
        data=_valid_form_data(title="Unauthorized change"),
    )
    assert response.status_code == 404

    with app.app_context():
        event = db.session.get(CampusEvent, event_id)
        assert event.title == "Route Test Event"


def test_student_cannot_view_published_event_from_another_campus(
    app, client, event_template_stub
):
    with app.app_context():
        campus_a = _make_campus()
        campus_b = _make_campus()

        student_id = _make_user(campus=campus_a)
        owner_id = _make_user(campus=campus_b)

        event_id = _make_event(
            campus=campus_b,
            organizer_id=owner_id,
            status="published",
        )

    _login(client, student_id)

    response = client.get(f"/events/{event_id}")
    assert response.status_code == 404


def test_student_can_rsvp_and_cancel_rsvp(app, client):
    with app.app_context():
        campus = _make_campus()
        student_id = _make_user(campus=campus)
        organizer_id = _make_user(campus=campus)

        event_id = _make_event(
            campus=campus,
            organizer_id=organizer_id,
            status="published",
        )

    _login(client, student_id)

    response = client.post(f"/events/{event_id}/rsvp")
    assert response.status_code == 302

    with app.app_context():
        rsvp = EventRSVP.query.filter_by(
            event_id=event_id,
            user_id=student_id,
        ).one()
        assert rsvp is not None

    response = client.post(f"/events/{event_id}/cancel-rsvp")
    assert response.status_code == 302

    with app.app_context():
        assert EventRSVP.query.filter_by(
            event_id=event_id,
            user_id=student_id,
        ).first() is None

def test_event_owner_can_submit_draft_for_review(app, client):
    with app.app_context():
        campus = _make_campus()
        user_id = _make_user(campus=campus)
        event_id = _make_event(
            campus=campus,
            organizer_id=user_id,
        )

    _login(client, user_id)

    response = client.post(f"/events/{event_id}/submit")
    assert response.status_code == 302

    with app.app_context():
        event = db.session.get(CampusEvent, event_id)
        assert event.status == "pending_review"


def test_student_cannot_submit_another_students_event(app, client):
    with app.app_context():
        campus = _make_campus()
        owner_id = _make_user(campus=campus)
        other_id = _make_user(campus=campus)
        event_id = _make_event(
            campus=campus,
            organizer_id=owner_id,
        )

    _login(client, other_id)

    response = client.post(f"/events/{event_id}/submit")
    assert response.status_code == 404

    with app.app_context():
        event = db.session.get(CampusEvent, event_id)
        assert event.status == "draft"


def test_editing_published_event_returns_it_to_review(app, client):
    with app.app_context():
        campus = _make_campus()
        user_id = _make_user(campus=campus)
        event_id = _make_event(
            campus=campus,
            organizer_id=user_id,
            status="published",
        )

    _login(client, user_id)

    response = client.post(
        f"/events/{event_id}/edit",
        data=_valid_form_data(title="Updated Published Event"),
    )
    assert response.status_code == 302

    with app.app_context():
        event = db.session.get(CampusEvent, event_id)
        assert event.title == "Updated Published Event"
        assert event.status == "pending_review"


def test_my_events_page_renders(app, client, event_template_stub):
    with app.app_context():
        campus = _make_campus()
        user_id = _make_user(campus=campus)

    _login(client, user_id)

    response = client.get("/events/mine")
    assert response.status_code == 200
    assert b"pages/events/my_events.html" in response.data


def test_registered_events_page_renders(app, client, event_template_stub):
    with app.app_context():
        campus = _make_campus()
        student_id = _make_user(campus=campus)
        organizer_id = _make_user(campus=campus)
        event_id = _make_event(
            campus=campus,
            organizer_id=organizer_id,
            status="published",
        )

        db.session.add(
            EventRSVP(
                event_id=event_id,
                user_id=student_id,
            )
        )
        db.session.commit()

    _login(client, student_id)

    response = client.get("/events/registered")
    assert response.status_code == 200
    assert b"pages/events/registered.html" in response.data


def test_student_cannot_rsvp_to_another_campus_event(app, client):
    with app.app_context():
        campus_a = _make_campus()
        campus_b = _make_campus()

        student_id = _make_user(campus=campus_a)
        organizer_id = _make_user(campus=campus_b)

        event_id = _make_event(
            campus=campus_b,
            organizer_id=organizer_id,
            status="published",
        )

    _login(client, student_id)

    response = client.post(f"/events/{event_id}/rsvp")
    assert response.status_code == 404

    with app.app_context():
        assert EventRSVP.query.filter_by(
            event_id=event_id,
            user_id=student_id,
        ).first() is None
def test_event_wat_converts_utc_across_midnight():
    utc_value = datetime(2026, 12, 31, 23, 30, tzinfo=timezone.utc)

    assert event_wat(utc_value, "%A, %B %d, %Y") == "Friday, January 01, 2027"
    assert event_wat(utc_value, "%I:%M %p") == "12:30 AM"


def test_event_wat_converts_timezone_aware_utc():
    utc_value = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)

    assert event_wat(utc_value, "%I:%M %p") == "01:00 PM"


def test_event_wat_assumes_naive_datetime_is_utc():
    utc_value = datetime(2026, 11, 27, 23, 30)

    assert event_wat(utc_value, "%I:%M %p") == "12:30 AM"
