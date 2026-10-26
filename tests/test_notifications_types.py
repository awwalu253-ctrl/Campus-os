"""Tests for the notification type registry and push eligibility.

Phase 3.10. Verifies that TASK_REMINDER was added to both:
  - the canonical REGISTRY (with the correct category)
  - the _PUSH_ELIGIBLE_TYPES set used by the push dispatch queue
"""
from app.notifications import types as ntypes
from app.notifications import services as notif_services


def test_task_reminder_in_registry():
    """TASK_REMINDER is a valid registered type with the correct metadata."""
    assert ntypes.TASK_REMINDER == "task_reminder"
    assert ntypes.is_valid(ntypes.TASK_REMINDER) is True

    meta = ntypes.meta(ntypes.TASK_REMINDER)
    assert meta is not None
    assert meta["label"] == "Task due soon"
    assert meta["category"] == "tasks"


def test_task_reminder_push_eligible():
    """TASK_REMINDER is included in the push-eligible set so its
    notifications dispatch via the after-commit listener."""
    assert ntypes.TASK_REMINDER in notif_services._PUSH_ELIGIBLE_TYPES


def test_existing_types_still_registered():
    """Adding TASK_REMINDER did not remove or rename existing types."""
    for key in (
        ntypes.REPORT_CONFIRMATION_MILESTONE,
        ntypes.REPORT_DISAGREEMENT,
        ntypes.REPORT_FLAGGED,
        ntypes.REPORT_EXPIRED_STALE,
        ntypes.CAMPUS_SAFETY_REPORT,
        ntypes.LOCATION_SUGGESTION_APPROVED,
        ntypes.LOCATION_SUGGESTION_REJECTED,
    ):
        assert ntypes.is_valid(key), f"Existing type missing from registry: {key}"


def test_existing_push_eligible_types_unchanged():
    """The two pre-existing push-eligible types are still eligible."""
    assert ntypes.CAMPUS_SAFETY_REPORT in notif_services._PUSH_ELIGIBLE_TYPES
    assert ntypes.REPORT_CONFIRMATION_MILESTONE in notif_services._PUSH_ELIGIBLE_TYPES