from datetime import datetime, timezone

from geoalchemy2.functions import ST_Distance, ST_MakePoint, ST_SetSRID
from sqlalchemy import and_, func, select

from app.extensions import db
from app.maps import categories as loc_cats
from app.maps.models import Location, LocationSuggestion
from app.notifications import services as notifications
from app.notifications import types as ntypes


# ── Read ──────────────────────────────────────────────────
def _location_rows(campus_id: str, *, category: str | None = None,
                   search: str | None = None, limit: int = 500):
    """Return rows of (Location, lat, lng) — coordinates fetched in the
    same query as the row itself, eliminating the previous N+1."""
    stmt = (
        select(
            Location,
            func.ST_Y(Location.point).label("lat"),
            func.ST_X(Location.point).label("lng"),
        )
        .where(and_(
            Location.campus_id == campus_id,
            Location.status == "approved",
        ))
    )
    if category:
        stmt = stmt.where(Location.category == category)
    if search:
        stmt = stmt.where(Location.name.ilike(f"%{search.strip()}%"))
    stmt = stmt.order_by(Location.name).limit(limit)
    return db.session.execute(stmt).all()


def approved_locations(campus_id: str, *, category: str | None = None,
                       search: str | None = None, limit: int = 500):
    """Kept for backward compatibility — returns ORM Location objects.

    Prefer `approved_locations_geo()` for API responses that need lat/lng."""
    rows = _location_rows(campus_id, category=category, search=search, limit=limit)
    return [row[0] for row in rows]


def approved_locations_geo(campus_id: str, *, category: str | None = None,
                           search: str | None = None, limit: int = 500) -> list[dict]:
    """Return serialized locations with lat/lng in a single query."""
    rows = _location_rows(campus_id, category=category, search=search, limit=limit)
    return [
        {
            "id": loc.id,
            "name": loc.name,
            "category": loc.category,
            "description": loc.description,
            "lat": float(lat) if lat is not None else None,
            "lng": float(lng) if lng is not None else None,
            "opening_hours": loc.opening_hours,
            "phone": loc.phone,
        }
        for loc, lat, lng in rows
    ]


def locations_near(campus_id: str, lat: float, lng: float, *,
                   radius_m: int = 300, limit: int = 50):
    """PostGIS nearest N approved locations within radius_m meters."""
    point = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
    distance = ST_Distance(Location.point, point)

    stmt = (
        select(
            Location,
            func.ST_Y(Location.point).label("lat"),
            func.ST_X(Location.point).label("lng"),
            distance.label("distance"),
        )
        .where(and_(
            Location.campus_id == campus_id,
            Location.status == "approved",
            func.ST_DWithin(Location.point, point, radius_m),
        ))
        .order_by(distance)
        .limit(limit)
    )
    return db.session.execute(stmt).all()


def get_location(location_id: str) -> Location | None:
    return db.session.get(Location, location_id)


def location_coords(location_id: str) -> tuple[float | None, float | None]:
    """Fetch only lat/lng for one location in a single query."""
    row = db.session.execute(
        select(
            func.ST_Y(Location.point),
            func.ST_X(Location.point),
        ).where(Location.id == location_id)
    ).first()
    if not row:
        return None, None
    return (
        float(row[0]) if row[0] is not None else None,
        float(row[1]) if row[1] is not None else None,
    )


def as_geojson(location: Location) -> dict:
    """Kept for the single-location detail page. For lists, use
    `approved_locations_geo()` which avoids the per-row query."""
    lat, lng = location_coords(location.id)
    return {
        "id": location.id,
        "name": location.name,
        "category": location.category,
        "description": location.description,
        "lat": lat,
        "lng": lng,
        "opening_hours": location.opening_hours,
        "phone": location.phone,
    }


# ── Admin: create / edit ──────────────────────────────────
def create_location(*, campus_id: str, name: str, category: str,
                    lat: float, lng: float,
                    description: str | None = None,
                    opening_hours: str | None = None,
                    phone: str | None = None,
                    created_by: str | None = None,
                    source: str = "admin",
                    status: str = "approved") -> Location:
    if not loc_cats.is_valid(category):
        raise ValueError(f"Unknown category: {category}")

    wkt_point = f"SRID=4326;POINT({lng} {lat})"
    loc = Location(
        campus_id=campus_id,
        name=name.strip()[:160],
        category=category,
        description=(description or "").strip()[:500] or None,
        point=wkt_point,
        opening_hours=(opening_hours or "").strip()[:120] or None,
        phone=(phone or "").strip()[:32] or None,
        source=source,
        status=status,
        created_by=created_by,
    )
    db.session.add(loc)
    db.session.flush()
    return loc


# ── Student suggestions ───────────────────────────────────
def suggest_location(*, campus_id: str, user_id: str, name: str, category: str,
                     lat: float, lng: float,
                     description: str | None = None) -> LocationSuggestion:
    if not loc_cats.is_valid(category):
        raise ValueError(f"Unknown category: {category}")

    sug = LocationSuggestion(
        campus_id=campus_id,
        proposed_by=user_id,
        name=name.strip()[:160],
        category=category,
        description=(description or "").strip()[:500] or None,
        lat=float(lat),
        lng=float(lng),
        status="pending",
    )
    db.session.add(sug)
    db.session.flush()
    return sug


def approve_suggestion(sug: LocationSuggestion, *, moderator_id: str,
                       note: str | None = None) -> Location:
    if sug.status != "pending":
        raise ValueError("Suggestion already moderated.")

    loc = create_location(
        campus_id=sug.campus_id,
        name=sug.name,
        category=sug.category,
        lat=sug.lat,
        lng=sug.lng,
        description=sug.description,
        created_by=sug.proposed_by,
        source="student",
        status="approved",
    )
    loc.verified_by = moderator_id
    loc.verified_at = datetime.now(timezone.utc)

    sug.status = "approved"
    sug.moderated_by = moderator_id
    sug.moderated_at = datetime.now(timezone.utc)
    sug.moderation_note = (note or "")[:255] or None
    sug.approved_location_id = loc.id

    # Notify the student who proposed the suggestion. The dedupe key
    # ensures exactly one approval notification per suggestion, even if
    # this function were ever re-run against the same row.
    if sug.proposed_by:
        notifications.create_notification_if_new(
            recipient_id=sug.proposed_by,
            type=ntypes.LOCATION_SUGGESTION_APPROVED,
            title="Your location suggestion was approved",
            body=(
                f'"{sug.name}" has been added to Campus OS. '
                "Thanks for helping map your campus."
            ),
            action_url=f"/map/location/{loc.id}",
            campus_id=sug.campus_id,
            related_entity_type="location_suggestion",
            related_entity_id=sug.id,
            dedupe_key=f"location-suggestion:{sug.id}:approved",
        )

    return loc


def reject_suggestion(sug: LocationSuggestion, *, moderator_id: str,
                      note: str | None = None) -> None:
    if sug.status != "pending":
        raise ValueError("Suggestion already moderated.")
    sug.status = "rejected"
    sug.moderated_by = moderator_id
    sug.moderated_at = datetime.now(timezone.utc)
    sug.moderation_note = (note or "")[:255] or None

    # Notify the student who proposed the suggestion. The moderation
    # note (if any) is moderator-only and intentionally NOT exposed to
    # the student — no reason to include it in the notification body.
    if sug.proposed_by:
        notifications.create_notification_if_new(
            recipient_id=sug.proposed_by,
            type=ntypes.LOCATION_SUGGESTION_REJECTED,
            title="Your location suggestion was not approved",
            body=(
                f'Your suggestion "{sug.name}" was reviewed '
                "but was not approved."
            ),
            action_url="/map/suggest",
            campus_id=sug.campus_id,
            related_entity_type="location_suggestion",
            related_entity_id=sug.id,
            dedupe_key=f"location-suggestion:{sug.id}:rejected",
        )


def pending_suggestions(campus_id: str | None = None, *, limit: int = 100):
    stmt = select(LocationSuggestion).where(LocationSuggestion.status == "pending")
    if campus_id:
        stmt = stmt.where(LocationSuggestion.campus_id == campus_id)
    stmt = stmt.order_by(LocationSuggestion.created_at.desc()).limit(limit)
    return db.session.execute(stmt).scalars().all()