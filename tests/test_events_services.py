
"""Tests for Campus Events business services.

Phase 2 covers event creation, ownership, campus isolation,
staff assignments, moderation, RSVP rules, and read queries.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.auth import services as auth_services
from app.events import services
from app.events.models import CampusEvent, EventRSVP
from app.extensions import db
from app.models import Campus, StudentProfile, University, User
from app.models.staff import StaffCampusAssignment


def _make_campus():
    suffix = uuid.uuid4().hex[:8]

    university = University(
        slug=f"service-test-{suffix}",
        name="Events Service University",
        short_name="ESU",
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
        email=f"service-{suffix}@example.com",
        password="testpass1234",
        display_name="Events Service Test",
    )

    user.role = role

    if campus is not None:
        user.profile = StudentProfile(
            university_id=campus.university_id,
            campus_id=campus.id,
        )

    db.session.commit()
    return user


def _event_times():
    starts_at = datetime.now(timezone.utc) + timedelta(days=3)
    return starts_at, starts_at + timedelta(hours=2)


def _make_event(*, campus, organizer, status="draft", capacity=None):
    starts_at, ends_at = _event_times()

    event = CampusEvent(
        campus_id=campus.id,
        organizer_id=organizer.id,
        title="Campus Tech Meetup",
        description="A student technology meetup.",
        category="technology",
        venue="Main Auditorium",
        starts_at=starts_at,
        ends_at=ends_at,
        status=status,
        capacity=capacity,
    )
    db.session.add(event)
    db.session.commit()
    return event


def _create_event(*, user, capacity=None, title="Campus Tech Meetup"):
    starts_at, ends_at = _event_times()

    return services.create_event(
        user=user,
        title=title,
        description="A student technology meetup.",
        category="technology",
        venue="Main Auditorium",
        starts_at=starts_at,
        ends_at=ends_at,
        capacity=capacity,
    )


# Student event creation and ownership


def test_create_event_uses_students_campus_and_starts_as_draft(app):
    with app.app_context():
        campus = _make_campus()
        student = _make_user(campus=campus)

        event = _create_event(
            user=student,
            title="  Student Tech Meetup  ",
        )

        assert event.campus_id == campus.id
        assert event.organizer_id == student.id
        assert event.status == "draft"
        assert event.title == "Student Tech Meetup"


def test_create_event_requires_student_campus_profile(app):
    with app.app_context():
        student = _make_user()

        with pytest.raises(ValueError, match="campus profile"):
            _create_event(user=student)


def test_non_student_cannot_create_event(app):
    with app.app_context():
        campus = _make_campus()
        moderator = _make_user(role="moderator")

        with pytest.raises(ValueError, match="Only students"):
            _create_event(user=moderator)


def test_create_event_rejects_invalid_category(app):
    with app.app_context():
        campus = _make_campus()
        student = _make_user(campus=campus)
        starts_at, ends_at = _event_times()

        with pytest.raises(ValueError, match="category"):
            services.create_event(
                user=student,
                title="Invalid Category Event",
                description="Description",
                category="not-a-category",
                venue="Main Hall",
                starts_at=starts_at,
                ends_at=ends_at,
            )


def test_student_cannot_edit_another_students_event(app):
    with app.app_context():
        campus = _make_campus()
        owner = _make_user(campus=campus)
        another_student = _make_user(campus=campus)
        event = _make_event(campus=campus, organizer=owner)

        starts_at, ends_at = _event_times()

        with pytest.raises(PermissionError, match="another student's"):
            services.update_event(
                event=event,
                user=another_student,
                title="Changed title",
                description=event.description,
                category=event.category,
                venue=event.venue,
                starts_at=starts_at,
                ends_at=ends_at,
            )


def test_published_event_edit_returns_event_to_review(app):
    with app.app_context():
        campus = _make_campus()
        student = _make_user(campus=campus)
        reviewer = _make_user(role="platform_admin")

        event = _make_event(
            campus=campus,
            organizer=student,
            status="published",
        )

        event.reviewed_by = reviewer.id
        event.reviewed_at = datetime.now(timezone.utc)
        event.published_at = datetime.now(timezone.utc)
        db.session.commit()

        starts_at, ends_at = _event_times()

        updated = services.update_event(
            event=event,
            user=student,
            title="Updated Tech Meetup",
            description=event.description,
            category=event.category,
            venue=event.venue,
            starts_at=starts_at,
            ends_at=ends_at,
        )

        assert updated.status == "pending_review"
        assert updated.reviewed_by is None
        assert updated.reviewed_at is None
        assert updated.published_at is None


def test_submit_event_moves_draft_to_pending_review(app):
    with app.app_context():
        campus = _make_campus()
        student = _make_user(campus=campus)
        event = _make_event(campus=campus, organizer=student)

        services.submit_event(event=event, user=student)

        assert event.status == "pending_review"


# Staff campus assignments


def test_platform_admin_can_assign_staff_to_campus(app):
    with app.app_context():
        campus = _make_campus()
        platform_admin = _make_user(role="platform_admin")
        moderator = _make_user(role="moderator")

        assignment = services.assign_staff_to_campus(
            actor=platform_admin,
            staff_user=moderator,
            campus_id=campus.id,
        )

        assert assignment.user_id == moderator.id
        assert assignment.campus_id == campus.id
        assert assignment.is_active is True


def test_non_platform_admin_cannot_assign_staff(app):
    with app.app_context():
        campus = _make_campus()
        campus_admin = _make_user(role="campus_admin")
        moderator = _make_user(role="moderator")

        with pytest.raises(PermissionError, match="Only platform admins"):
            services.assign_staff_to_campus(
                actor=campus_admin,
                staff_user=moderator,
                campus_id=campus.id,
            )


def test_revoked_assignment_removes_campus_access(app):
    with app.app_context():
        campus = _make_campus()
        platform_admin = _make_user(role="platform_admin")
        moderator = _make_user(role="moderator")

        assignment = services.assign_staff_to_campus(
            actor=platform_admin,
            staff_user=moderator,
            campus_id=campus.id,
        )

        services.revoke_staff_campus_assignment(
            actor=platform_admin,
            assignment_id=assignment.id,
        )

        assert assignment.is_active is False
        assert services._has_campus_access(moderator, campus.id) is False


def test_staff_cannot_moderate_unassigned_campus_event(app):
    with app.app_context():
        campus = _make_campus()
        student = _make_user(campus=campus)
        moderator = _make_user(role="moderator")

        event = _make_event(
            campus=campus,
            organizer=student,
            status="pending_review",
        )

        with pytest.raises(PermissionError, match="not assigned"):
            services.approve_event(event=event, reviewer=moderator)


# Moderation


def test_assigned_moderator_can_approve_event(app):
    with app.app_context():
        campus = _make_campus()
        student = _make_user(campus=campus)
        platform_admin = _make_user(role="platform_admin")
        moderator = _make_user(role="moderator")

        services.assign_staff_to_campus(
            actor=platform_admin,
            staff_user=moderator,
            campus_id=campus.id,
        )

        event = _make_event(
            campus=campus,
            organizer=student,
            status="pending_review",
        )

        services.approve_event(event=event, reviewer=moderator)

        assert event.status == "published"
        assert event.reviewed_by == moderator.id
        assert event.reviewed_at is not None
        assert event.published_at is not None


def test_reject_event_requires_reason(app):
    with app.app_context():
        campus = _make_campus()
        student = _make_user(campus=campus)
        platform_admin = _make_user(role="platform_admin")

        event = _make_event(
            campus=campus,
            organizer=student,
            status="pending_review",
        )

        with pytest.raises(ValueError, match="rejection reason"):
            services.reject_event(
                event=event,
                reviewer=platform_admin,
                reason="   ",
            )


def test_platform_admin_can_reject_event_with_reason(app):
    with app.app_context():
        campus = _make_campus()
        student = _make_user(campus=campus)
        platform_admin = _make_user(role="platform_admin")

        event = _make_event(
            campus=campus,
            organizer=student,
            status="pending_review",
        )

        services.reject_event(
            event=event,
            reviewer=platform_admin,
            reason="Please provide more event details.",
        )

        assert event.status == "rejected"
        assert event.reviewed_by == platform_admin.id
        assert event.reviewed_at is not None
        assert event.rejection_reason == "Please provide more event details."


def test_review_queue_only_returns_assigned_campus_events(app):
    with app.app_context():
        campus_one = _make_campus()
        campus_two = _make_campus()

        student_one = _make_user(campus=campus_one)
        student_two = _make_user(campus=campus_two)
        platform_admin = _make_user(role="platform_admin")
        moderator = _make_user(role="moderator")

        services.assign_staff_to_campus(
            actor=platform_admin,
            staff_user=moderator,
            campus_id=campus_one.id,
        )

        event_one = _make_event(
            campus=campus_one,
            organizer=student_one,
            status="pending_review",
        )
        _make_event(
            campus=campus_two,
            organizer=student_two,
            status="pending_review",
        )

        queue = services.review_queue(moderator)

        assert [event.id for event in queue] == [event_one.id]


# RSVPs and capacity


def test_student_can_rsvp_to_published_same_campus_event(app):
    with app.app_context():
        campus = _make_campus()
        organizer = _make_user(campus=campus)
        attendee = _make_user(campus=campus)

        event = _make_event(
            campus=campus,
            organizer=organizer,
            status="published",
        )

        rsvp = services.rsvp_to_event(
            event_id=event.id,
            user=attendee,
        )

        assert rsvp.event_id == event.id
        assert rsvp.user_id == attendee.id


def test_student_cannot_rsvp_to_another_campus_event(app):
    with app.app_context():
        campus_one = _make_campus()
        campus_two = _make_campus()

        organizer = _make_user(campus=campus_one)
        attendee = _make_user(campus=campus_two)

        event = _make_event(
            campus=campus_one,
            organizer=organizer,
            status="published",
        )

        with pytest.raises(ValueError, match="does not exist"):
            services.rsvp_to_event(
                event_id=event.id,
                user=attendee,
            )


def test_student_cannot_rsvp_twice(app):
    with app.app_context():
        campus = _make_campus()
        organizer = _make_user(campus=campus)
        attendee = _make_user(campus=campus)

        event = _make_event(
            campus=campus,
            organizer=organizer,
            status="published",
        )

        services.rsvp_to_event(event_id=event.id, user=attendee)

        with pytest.raises(ValueError, match="already registered"):
            services.rsvp_to_event(event_id=event.id, user=attendee)


def test_event_capacity_is_enforced(app):
    with app.app_context():
        campus = _make_campus()
        organizer = _make_user(campus=campus)
        attendee_one = _make_user(campus=campus)
        attendee_two = _make_user(campus=campus)

        event = _make_event(
            campus=campus,
            organizer=organizer,
            status="published",
            capacity=1,
        )

        services.rsvp_to_event(
            event_id=event.id,
            user=attendee_one,
        )

        with pytest.raises(ValueError, match="full"):
            services.rsvp_to_event(
                event_id=event.id,
                user=attendee_two,
            )


def test_student_can_cancel_own_rsvp(app):
    with app.app_context():
        campus = _make_campus()
        organizer = _make_user(campus=campus)
        attendee = _make_user(campus=campus)

        event = _make_event(
            campus=campus,
            organizer=organizer,
            status="published",
        )

        services.rsvp_to_event(event_id=event.id, user=attendee)
        services.cancel_rsvp(event_id=event.id, user=attendee)

        remaining = db.session.query(EventRSVP).filter_by(
            event_id=event.id,
            user_id=attendee.id,
        ).first()

        assert remaining is None


# Read queries


def test_published_events_for_user_only_returns_same_campus_events(app):
    with app.app_context():
        campus_one = _make_campus()
        campus_two = _make_campus()

        student = _make_user(campus=campus_one)
        organizer_one = _make_user(campus=campus_one)
        organizer_two = _make_user(campus=campus_two)

        same_campus_event = _make_event(
            campus=campus_one,
            organizer=organizer_one,
            status="published",
        )
        _make_event(
            campus=campus_two,
            organizer=organizer_two,
            status="published",
        )

        results = services.published_events_for_user(student)

        assert [event.id for event in results] == [same_campus_event.id]


def test_my_created_events_only_returns_users_own_events(app):
    with app.app_context():
        campus = _make_campus()
        student_one = _make_user(campus=campus)
        student_two = _make_user(campus=campus)

        own_event = _make_event(campus=campus, organizer=student_one)
        _make_event(campus=campus, organizer=student_two)

        results = services.my_created_events(student_one)

        assert [event.id for event in results] == [own_event.id]
