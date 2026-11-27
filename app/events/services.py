"""Business logic for Campus OS events.

Services do not depend on Flask request state and do not commit.
The caller owns transaction commit/rollback.
"""

from datetime import datetime, timezone

from sqlalchemy import func, select

from app.extensions import db
from app.events import categories
from app.events.models import CampusEvent, EventRSVP
from app.models.staff import StaffCampusAssignment
from app.models.university import Campus
from app.models.user import User


_STAFF_ROLES = {"moderator", "campus_admin"}
_STUDENT_ROLE = "student"

_EVENT_FIELDS = (
    "title",
    "description",
    "category",
    "venue",
    "starts_at",
    "ends_at",
    "capacity",
)


def _require_active_user(user):
    if not user or not user.is_active:
        raise ValueError("An active user account is required.")


def _require_student(user):
    _require_active_user(user)

    if user.role != _STUDENT_ROLE:
        raise ValueError("Only students can perform this action.")


def _require_staff(user):
    _require_active_user(user)

    if user.role not in _STAFF_ROLES | {"platform_admin"}:
        raise PermissionError("You are not authorized to moderate events.")


def _student_campus_id(user) -> str:
    _require_student(user)

    profile = user.profile
    if not profile or not profile.campus_id:
        raise ValueError("Complete your campus profile before using Events.")

    return profile.campus_id


def _has_campus_access(user, campus_id: str) -> bool:
    if user.role == "platform_admin":
        return True

    if user.role not in _STAFF_ROLES:
        return False

    assignment = db.session.execute(
        select(StaffCampusAssignment.id).where(
            StaffCampusAssignment.user_id == user.id,
            StaffCampusAssignment.campus_id == campus_id,
            StaffCampusAssignment.is_active.is_(True),
        )
    ).scalar_one_or_none()

    return assignment is not None


def _require_event_owner(event: CampusEvent, user):
    _require_student(user)

    if event.organizer_id != user.id:
        raise PermissionError("You cannot manage another student's event.")


def _require_event_reviewer(event: CampusEvent, reviewer):
    _require_staff(reviewer)

    if not _has_campus_access(reviewer, event.campus_id):
        raise PermissionError("You are not assigned to this campus.")


def _validate_event_fields(
    *,
    title,
    description,
    category,
    venue,
    starts_at,
    ends_at,
    capacity,
):
    title = (title or "").strip()
    description = (description or "").strip()
    category = (category or "").strip()
    venue = (venue or "").strip()

    if not title or len(title) > 160:
        raise ValueError("Title is required and must be at most 160 characters.")

    if not description or len(description) > 3000:
        raise ValueError("Description is required and must be at most 3000 characters.")

    if not categories.is_valid(category):
        raise ValueError("Choose a valid event category.")

    if not venue or len(venue) > 180:
        raise ValueError("Venue is required and must be at most 180 characters.")

    if not isinstance(starts_at, datetime) or not isinstance(ends_at, datetime):
        raise ValueError("Valid event start and end dates are required.")

    if starts_at.tzinfo is None or starts_at.utcoffset() is None:
        raise ValueError("Event start time must include a timezone.")

    if ends_at.tzinfo is None or ends_at.utcoffset() is None:
        raise ValueError("Event end time must include a timezone.")

    if ends_at <= starts_at:
        raise ValueError("Event end time must be after its start time.")

    if starts_at <= datetime.now(timezone.utc):
        raise ValueError("Event start time must be in the future.")

    if capacity is not None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity < 1:
            raise ValueError("Capacity must be a positive whole number.")

    return {
        "title": title,
        "description": description,
        "category": category,
        "venue": venue,
        "starts_at": starts_at,
        "ends_at": ends_at,
        "capacity": capacity,
    }


# ---------------------------------------------------------------------------
# Staff-campus assignment management
# ---------------------------------------------------------------------------

def assign_staff_to_campus(
    *,
    actor,
    staff_user,
    campus_id: str,
) -> StaffCampusAssignment:
    """Create or reactivate a staff member's campus assignment.

    Only platform admins can manage assignments initially.
    """
    _require_active_user(actor)

    if actor.role != "platform_admin":
        raise PermissionError("Only platform admins can assign campus staff.")

    if not staff_user or not staff_user.is_active:
        raise ValueError("An active staff account is required.")

    if staff_user.role not in _STAFF_ROLES:
        raise ValueError("Only moderators and campus admins can be assigned.")

    if not db.session.get(Campus, campus_id):
        raise ValueError("Campus does not exist.")

    assignment = db.session.execute(
        select(StaffCampusAssignment).where(
            StaffCampusAssignment.user_id == staff_user.id,
            StaffCampusAssignment.campus_id == campus_id,
        )
    ).scalar_one_or_none()

    if assignment:
        if assignment.is_active:
            raise ValueError("This staff member is already assigned to the campus.")

        assignment.is_active = True
        assignment.assigned_by = actor.id
    else:
        assignment = StaffCampusAssignment(
            user_id=staff_user.id,
            campus_id=campus_id,
            assigned_by=actor.id,
            is_active=True,
        )
        db.session.add(assignment)

    db.session.flush()
    return assignment


def revoke_staff_campus_assignment(
    *,
    actor,
    assignment_id: str,
) -> StaffCampusAssignment:
    _require_active_user(actor)

    if actor.role != "platform_admin":
        raise PermissionError("Only platform admins can revoke campus assignments.")

    assignment = db.session.get(StaffCampusAssignment, assignment_id)

    if not assignment:
        raise ValueError("Campus assignment does not exist.")

    if not assignment.is_active:
        raise ValueError("Campus assignment is already inactive.")

    assignment.is_active = False
    db.session.flush()
    return assignment


# ---------------------------------------------------------------------------
# Student event creation and editing
# ---------------------------------------------------------------------------

def create_event(
    *,
    user,
    title,
    description,
    category,
    venue,
    starts_at,
    ends_at,
    capacity=None,
) -> CampusEvent:
    campus_id = _student_campus_id(user)

    values = _validate_event_fields(
        title=title,
        description=description,
        category=category,
        venue=venue,
        starts_at=starts_at,
        ends_at=ends_at,
        capacity=capacity,
    )

    event = CampusEvent(
        campus_id=campus_id,
        organizer_id=user.id,
        status="draft",
        **values,
    )

    db.session.add(event)
    db.session.flush()
    return event


def update_event(
    *,
    event: CampusEvent,
    user,
    title,
    description,
    category,
    venue,
    starts_at,
    ends_at,
    capacity=None,
) -> CampusEvent:
    _require_event_owner(event, user)

    if event.status not in {"draft", "rejected", "pending_review", "published"}:
        raise ValueError("This event cannot be edited in its current state.")

    values = _validate_event_fields(
        title=title,
        description=description,
        category=category,
        venue=venue,
        starts_at=starts_at,
        ends_at=ends_at,
        capacity=capacity,
    )

    changed = any(
        getattr(event, field) != value
        for field, value in values.items()
    )

    if not changed:
        return event

    for field, value in values.items():
        setattr(event, field, value)

    # A changed published event must be reviewed again.
    if event.status == "published":
        event.status = "pending_review"
        event.reviewed_by = None
        event.reviewed_at = None
        event.rejection_reason = None
        event.published_at = None

    # A pending event remains pending when its organizer edits it.
    # A rejected event remains rejected until explicitly resubmitted.
    db.session.flush()
    return event


def submit_event(*, event: CampusEvent, user) -> CampusEvent:
    _require_event_owner(event, user)

    if event.status not in {"draft", "rejected"}:
        raise ValueError("Only draft or rejected events can be submitted.")

    event.status = "pending_review"
    event.reviewed_by = None
    event.reviewed_at = None
    event.rejection_reason = None
    event.published_at = None

    db.session.flush()
    return event


# ---------------------------------------------------------------------------
# Staff moderation
# ---------------------------------------------------------------------------

def approve_event(*, event: CampusEvent, reviewer) -> CampusEvent:
    _require_event_reviewer(event, reviewer)

    if event.status != "pending_review":
        raise ValueError("Only events awaiting review can be approved.")

    now = datetime.now(timezone.utc)

    event.status = "published"
    event.reviewed_by = reviewer.id
    event.reviewed_at = now
    event.published_at = now
    event.rejection_reason = None

    db.session.flush()
    return event


def reject_event(
    *,
    event: CampusEvent,
    reviewer,
    reason: str,
) -> CampusEvent:
    _require_event_reviewer(event, reviewer)

    if event.status != "pending_review":
        raise ValueError("Only events awaiting review can be rejected.")

    reason = (reason or "").strip()

    if not reason:
        raise ValueError("A rejection reason is required.")

    if len(reason) > 1000:
        raise ValueError("Rejection reason must be at most 1000 characters.")

    event.status = "rejected"
    event.reviewed_by = reviewer.id
    event.reviewed_at = datetime.now(timezone.utc)
    event.rejection_reason = reason
    event.published_at = None

    db.session.flush()
    return event


# ---------------------------------------------------------------------------
# RSVPs
# ---------------------------------------------------------------------------

def rsvp_to_event(*, event_id: str, user) -> EventRSVP:
    campus_id = _student_campus_id(user)

    # Lock the event row so concurrent RSVP requests for this event
    # cannot both claim the final available place.
    event = db.session.execute(
        select(CampusEvent)
        .where(CampusEvent.id == event_id)
        .with_for_update()
    ).scalar_one_or_none()

    if not event or event.campus_id != campus_id:
        raise ValueError("Event does not exist.")

    if event.status != "published":
        raise ValueError("This event is not open for registration.")

    if event.starts_at <= datetime.now(timezone.utc):
        raise ValueError("Registration for this event has closed.")

    existing = db.session.execute(
        select(EventRSVP.id).where(
            EventRSVP.event_id == event.id,
            EventRSVP.user_id == user.id,
        )
    ).scalar_one_or_none()

    if existing:
        raise ValueError("You have already registered for this event.")

    if event.capacity is not None:
        registered = db.session.execute(
            select(func.count(EventRSVP.id)).where(
                EventRSVP.event_id == event.id
            )
        ).scalar_one()

        if registered >= event.capacity:
            raise ValueError("This event is full.")

    rsvp = EventRSVP(
        event_id=event.id,
        user_id=user.id,
    )

    db.session.add(rsvp)
    db.session.flush()
    return rsvp


def cancel_rsvp(*, event_id: str, user) -> None:
    _require_student(user)

    rsvp = db.session.execute(
        select(EventRSVP).where(
            EventRSVP.event_id == event_id,
            EventRSVP.user_id == user.id,
        )
    ).scalar_one_or_none()

    if not rsvp:
        raise ValueError("You are not registered for this event.")

    db.session.delete(rsvp)
    db.session.flush()


# ---------------------------------------------------------------------------
# Read queries
# ---------------------------------------------------------------------------

def published_events_for_user(user, *, limit: int = 100):
    campus_id = _student_campus_id(user)

    return db.session.execute(
        select(CampusEvent)
        .where(
            CampusEvent.campus_id == campus_id,
            CampusEvent.status == "published",
            CampusEvent.ends_at > datetime.now(timezone.utc),
        )
        .order_by(CampusEvent.starts_at.asc())
        .limit(limit)
    ).scalars().all()


def my_created_events(user, *, limit: int = 100):
    _require_student(user)

    return db.session.execute(
        select(CampusEvent)
        .where(CampusEvent.organizer_id == user.id)
        .order_by(CampusEvent.created_at.desc())
        .limit(limit)
    ).scalars().all()


def my_registered_events(user, *, limit: int = 100):
    _require_student(user)

    return db.session.execute(
        select(CampusEvent)
        .join(EventRSVP, EventRSVP.event_id == CampusEvent.id)
        .where(EventRSVP.user_id == user.id)
        .order_by(CampusEvent.starts_at.asc())
        .limit(limit)
    ).scalars().all()


def review_queue(reviewer, *, campus_id: str | None = None, limit: int = 100):
    _require_staff(reviewer)

    stmt = select(CampusEvent).where(
        CampusEvent.status == "pending_review"
    )

    if reviewer.role == "platform_admin":
        if campus_id:
            stmt = stmt.where(CampusEvent.campus_id == campus_id)
    else:
        assignments = select(StaffCampusAssignment.campus_id).where(
            StaffCampusAssignment.user_id == reviewer.id,
            StaffCampusAssignment.is_active.is_(True),
        )

        if campus_id:
            if not _has_campus_access(reviewer, campus_id):
                raise PermissionError("You are not assigned to this campus.")
            stmt = stmt.where(CampusEvent.campus_id == campus_id)
        else:
            stmt = stmt.where(CampusEvent.campus_id.in_(assignments))

    return db.session.execute(
        stmt.order_by(CampusEvent.created_at.asc()).limit(limit)
    ).scalars().all()

def get_event_for_review(*, event_id: str, reviewer):
    """Return a pending event only if the reviewer can access its campus."""
    _require_staff(reviewer)

    event = db.session.get(CampusEvent, event_id)
    if event is None:
        raise LookupError("Event not found.")

    _require_event_reviewer(event, reviewer)

    if event.status != "pending_review":
        raise ValueError("This event is no longer awaiting review.")

    return event