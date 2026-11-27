
"""Tests for Campus Events database models.

Phase 1 covers model defaults, constraints, unique RSVPs,
and foreign-key deletion behavior. Route and service tests
will be added in later phases.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.auth import services as auth_services
from app.extensions import db
from app.models import Campus, University, User
from app.events.models import (
    CampusEvent,
    EventRSVP,
    EVENT_STATUSES,
)


def _make_user():
    suffix = uuid.uuid4().hex[:8]

    user = auth_services.create_user(
        email=f"event-{suffix}@example.com",
        password="testpass1234",
        display_name="Events Test",
    )

    db.session.commit()
    return user.id


def _make_campus():
    suffix = uuid.uuid4().hex[:8]

    university = University(
        slug=f"event-test-{suffix}",
        name="Events Test University",
        short_name="ETU",
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

    return campus.id


def _make_event(campus_id, organizer_id, **overrides):
    starts_at = datetime.now(timezone.utc) + timedelta(days=2)

    values = {
        "campus_id": campus_id,
        "organizer_id": organizer_id,
        "title": "Campus Tech Meetup",
        "description": "A student technology meetup.",
        "category": "technology",
        "venue": "Main Auditorium",
        "starts_at": starts_at,
        "ends_at": starts_at + timedelta(hours=2),
    }

    values.update(overrides)

    event = CampusEvent(**values)
    db.session.add(event)
    db.session.commit()

    return event


def test_event_defaults_and_timestamps(app):
    with app.app_context():
        campus_id = _make_campus()
        organizer_id = _make_user()

        event = _make_event(campus_id, organizer_id)

        assert isinstance(event.id, str)
        assert len(event.id) == 36

        assert event.status == "draft"
        assert event.capacity is None
        assert event.reviewed_by is None
        assert event.reviewed_at is None
        assert event.rejection_reason is None
        assert event.published_at is None

        assert event.created_at is not None
        assert event.updated_at is not None


def test_event_status_vocabulary():
    assert EVENT_STATUSES == (
        "draft",
        "pending_review",
        "published",
        "rejected",
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"capacity": 0},
        {"capacity": -1},
        {"status": "unknown"},
    ],
)
def test_event_rejects_invalid_database_values(app, overrides):
    with app.app_context():
        campus_id = _make_campus()
        organizer_id = _make_user()

        starts_at = datetime.now(timezone.utc) + timedelta(days=2)

        event = CampusEvent(
            campus_id=campus_id,
            organizer_id=organizer_id,
            title="Invalid Event",
            description="This should not be saved.",
            category="technology",
            venue="Main Auditorium",
            starts_at=starts_at,
            ends_at=starts_at + timedelta(hours=2),
            **overrides,
        )

        db.session.add(event)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()


def test_event_rejects_end_time_before_start_time(app):
    with app.app_context():
        campus_id = _make_campus()
        organizer_id = _make_user()

        starts_at = datetime.now(timezone.utc) + timedelta(days=2)

        event = CampusEvent(
            campus_id=campus_id,
            organizer_id=organizer_id,
            title="Invalid Time Event",
            description="Invalid event time range.",
            category="technology",
            venue="Main Auditorium",
            starts_at=starts_at,
            ends_at=starts_at - timedelta(hours=1),
        )

        db.session.add(event)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()


def test_event_allows_unlimited_capacity(app):
    with app.app_context():
        campus_id = _make_campus()
        organizer_id = _make_user()

        event = _make_event(
            campus_id,
            organizer_id,
            capacity=None,
        )

        assert event.capacity is None


def test_event_rsvp_unique_per_user(app):
    with app.app_context():
        campus_id = _make_campus()
        organizer_id = _make_user()
        attendee_id = _make_user()

        event = _make_event(campus_id, organizer_id)

        first_rsvp = EventRSVP(
            event_id=event.id,
            user_id=attendee_id,
        )

        db.session.add(first_rsvp)
        db.session.commit()

        duplicate_rsvp = EventRSVP(
            event_id=event.id,
            user_id=attendee_id,
        )

        db.session.add(duplicate_rsvp)

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()


def test_deleting_event_cascades_to_rsvps(app):
    with app.app_context():
        campus_id = _make_campus()
        organizer_id = _make_user()
        attendee_id = _make_user()

        event = _make_event(campus_id, organizer_id)

        rsvp = EventRSVP(
            event_id=event.id,
            user_id=attendee_id,
        )

        db.session.add(rsvp)
        db.session.commit()

        event_id = event.id
        rsvp_id = rsvp.id

        db.session.delete(event)
        db.session.commit()

        assert db.session.get(CampusEvent, event_id) is None
        assert db.session.get(EventRSVP, rsvp_id) is None


def test_deleting_reviewer_preserves_event(app):
    with app.app_context():
        campus_id = _make_campus()
        organizer_id = _make_user()
        reviewer_id = _make_user()

        event = _make_event(
            campus_id,
            organizer_id,
            status="published",
            reviewed_by=reviewer_id,
            reviewed_at=datetime.now(timezone.utc),
        )

        event_id = event.id

        reviewer = db.session.get(User, reviewer_id)
        db.session.delete(reviewer)
        db.session.commit()

        preserved_event = db.session.get(CampusEvent, event_id)

        assert preserved_event is not None
        assert preserved_event.reviewed_by is None
