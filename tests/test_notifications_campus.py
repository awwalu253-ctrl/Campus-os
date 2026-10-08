"""Tests for campus-wide safety/environment report notifications.

Covers the fan-out path added to create_report(): a report in a
Safety or Environment category notifies every active student on the
same campus, excluding the reporter. Ordinary reports notify nobody.
"""
import uuid

import pytest

from app.auth import services as auth_services
from app.extensions import db
from app.models import Campus, University
from app.models.user import StudentProfile
from app.notifications.models import Notification
from app.notifications import services as notif_services
from app.pulse import services as pulse_services


@pytest.fixture
def campus_setup(app):
    """Two universities, two campuses, several users.

    Campus A: reporter_a, student_a1, student_a2 (all active)
    Campus B: student_b1

    Returns a dict of ids.
    """
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]

        uni_a = University(slug=f"uni-a-{suffix}", name=f"Uni A {suffix}",
                           short_name=f"UA{suffix}")
        uni_b = University(slug=f"uni-b-{suffix}", name=f"Uni B {suffix}",
                           short_name=f"UB{suffix}")
        db.session.add_all([uni_a, uni_b])
        db.session.flush()

        campus_a = Campus(university_id=uni_a.id, slug="main", name="Campus A")
        campus_b = Campus(university_id=uni_b.id, slug="main", name="Campus B")
        db.session.add_all([campus_a, campus_b])
        db.session.flush()

        def make_user(email_prefix, campus):
            u = auth_services.create_user(
                email=f"{email_prefix}-{suffix}@example.com",
                password="testpass1234",
                display_name=email_prefix,
            )
            u.profile = StudentProfile(
                user_id=u.id,
                university_id=campus.university_id,
                campus_id=campus.id,
            )
            db.session.add(u.profile)
            return u

        reporter_a = make_user("reporter_a", campus_a)
        student_a1 = make_user("student_a1", campus_a)
        student_a2 = make_user("student_a2", campus_a)
        student_b1 = make_user("student_b1", campus_b)
        db.session.commit()

        return {
            "campus_a_id": campus_a.id,
            "campus_b_id": campus_b.id,
            "reporter_a_id": reporter_a.id,
            "student_a1_id": student_a1.id,
            "student_a2_id": student_a2.id,
            "student_b1_id": student_b1.id,
        }


def _count_campus_notifications(user_id):
    return Notification.query.filter_by(
        recipient_id=user_id,
        type="campus_safety_report",
    ).count()


def test_safety_report_notifies_same_campus(app, campus_setup):
    with app.app_context():
        from app.models import User
        reporter = db.session.get(User, campus_setup["reporter_a_id"])
        pulse_services.create_report(
            user=reporter,
            campus_id=campus_setup["campus_a_id"],
            category="suspicious_activity",
            description="Something suspicious",
        )
        db.session.commit()

        assert _count_campus_notifications(campus_setup["student_a1_id"]) == 1
        assert _count_campus_notifications(campus_setup["student_a2_id"]) == 1
        assert _count_campus_notifications(campus_setup["reporter_a_id"]) == 0
        assert _count_campus_notifications(campus_setup["student_b1_id"]) == 0


def test_environment_report_notifies_same_campus(app, campus_setup):
    with app.app_context():
        from app.models import User
        reporter = db.session.get(User, campus_setup["reporter_a_id"])
        pulse_services.create_report(
            user=reporter,
            campus_id=campus_setup["campus_a_id"],
            category="flooding",
            description="Flooding near the gate",
        )
        db.session.commit()

        assert _count_campus_notifications(campus_setup["student_a1_id"]) == 1
        assert _count_campus_notifications(campus_setup["student_b1_id"]) == 0


def test_ordinary_report_does_not_notify_campus(app, campus_setup):
    with app.app_context():
        from app.models import User
        reporter = db.session.get(User, campus_setup["reporter_a_id"])
        pulse_services.create_report(
            user=reporter,
            campus_id=campus_setup["campus_a_id"],
            category="water_outage",
            description="No water",
        )
        db.session.commit()

        assert _count_campus_notifications(campus_setup["student_a1_id"]) == 0
        assert _count_campus_notifications(campus_setup["student_a2_id"]) == 0


def test_reporter_does_not_receive_own_notification(app, campus_setup):
    with app.app_context():
        from app.models import User
        reporter = db.session.get(User, campus_setup["reporter_a_id"])
        pulse_services.create_report(
            user=reporter,
            campus_id=campus_setup["campus_a_id"],
            category="emergency",
            description="Emergency",
        )
        db.session.commit()

        assert _count_campus_notifications(campus_setup["reporter_a_id"]) == 0


def test_cross_campus_isolation(app, campus_setup):
    with app.app_context():
        from app.models import User
        reporter = db.session.get(User, campus_setup["reporter_a_id"])
        pulse_services.create_report(
            user=reporter,
            campus_id=campus_setup["campus_a_id"],
            category="dangerous_area",
            description="Dangerous area",
        )
        db.session.commit()

        assert _count_campus_notifications(campus_setup["student_b1_id"]) == 0


def test_each_eligible_recipient_gets_exactly_one(app, campus_setup):
    with app.app_context():
        from app.models import User
        reporter = db.session.get(User, campus_setup["reporter_a_id"])
        pulse_services.create_report(
            user=reporter,
            campus_id=campus_setup["campus_a_id"],
            category="suspicious_activity",
            description="One",
        )
        db.session.commit()

        assert _count_campus_notifications(campus_setup["student_a1_id"]) == 1
        assert _count_campus_notifications(campus_setup["student_a2_id"]) == 1


def test_repeated_creation_does_not_duplicate(app, campus_setup):
    """Calling the fan-out twice for the same report must not create
    duplicates, thanks to the (recipient_id, dedupe_key) unique index.
    """
    with app.app_context():
        from app.models import User
        reporter = db.session.get(User, campus_setup["reporter_a_id"])
        report = pulse_services.create_report(
            user=reporter,
            campus_id=campus_setup["campus_a_id"],
            category="suspicious_activity",
            description="Retry test",
        )
        db.session.commit()

        # Simulate a retry of the fan-out path for the same report.
        pulse_services._notify_campus_of_report(report, reporter_id=reporter.id)
        db.session.commit()

        assert _count_campus_notifications(campus_setup["student_a1_id"]) == 1
        assert _count_campus_notifications(campus_setup["student_a2_id"]) == 1


def test_action_url_points_to_correct_report(app, campus_setup):
    with app.app_context():
        from app.models import User
        reporter = db.session.get(User, campus_setup["reporter_a_id"])
        report = pulse_services.create_report(
            user=reporter,
            campus_id=campus_setup["campus_a_id"],
            category="suspicious_activity",
            description="URL test",
        )
        db.session.commit()

        n = Notification.query.filter_by(
            recipient_id=campus_setup["student_a1_id"],
            type="campus_safety_report",
        ).first()
        assert n is not None
        assert n.action_url == f"/pulse/report/{report.id}"
        assert n.related_entity_id == report.id
        assert n.campus_id == campus_setup["campus_a_id"]


def test_report_still_created_normally(app, campus_setup):
    """The fan-out must not alter the report row itself."""
    with app.app_context():
        from app.models import User
        reporter = db.session.get(User, campus_setup["reporter_a_id"])
        report = pulse_services.create_report(
            user=reporter,
            campus_id=campus_setup["campus_a_id"],
            category="water_outage",
            description="Normal flow",
        )
        db.session.commit()

        assert report.id is not None
        assert report.status == "active"
        assert report.category == "water_outage"
        assert report.reported_by == campus_setup["reporter_a_id"]
        assert report.confirmation_count == 0
        assert report.expires_at is not None