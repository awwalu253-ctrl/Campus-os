from datetime import datetime, timezone

from geoalchemy2.functions import ST_Distance, ST_MakePoint, ST_SetSRID
from sqlalchemy import and_, func, select

from app.extensions import db
from app.maps import categories as loc_cats
from app.maps.models import Location, LocationSuggestion


# ── Read ──────────────────────────────────────────────────
def approved_locations(campus_id: str, *, category: str | None = None,
                       search: str | None = None, limit: int = 500):
    stmt = select(Location).where(and_(
        Location.campus_id == campus_id,
        Location.status == "approved",
    ))
    if category:
        stmt = stmt.where(Location.category == category)
    if search:
        like = f"%{search.strip()}%"
        stmt = stmt.where(Location.name.ilike(like))
    stmt = stmt.order_by(Location.name).limit(limit)
    return db.session.execute(stmt).scalars().all()


def locations_near(campus_id: str, lat: float, lng: float, *,
                   radius_m: int = 300, limit: int = 50):
    """PostGIS: nearest N approved locations within radius_m meters."""
    point = ST_SetSRID(ST_MakePoint(lng, lat), 4326)
    distance = ST_Distance(Location.point, point)

    stmt = (
        select(Location, distance.label("distance"))
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


def as_geojson(location: Location) -> dict:
    """Serialize a Location row for the map frontend."""
    # ST_X / ST_Y extraction
    lat = db.session.execute(
        select(func.ST_Y(Location.point)).where(Location.id == location.id)
    ).scalar()
    lng = db.session.execute(
        select(func.ST_X(Location.point)).where(Location.id == location.id)
    ).scalar()
    return {
        "id": location.id,
        "name": location.name,
        "category": location.category,
        "description": location.description,
        "lat": float(lat) if lat is not None else None,
        "lng": float(lng) if lng is not None else None,
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
    return loc


def reject_suggestion(sug: LocationSuggestion, *, moderator_id: str,
                      note: str | None = None) -> None:
    if sug.status != "pending":
        raise ValueError("Suggestion already moderated.")
    sug.status = "rejected"
    sug.moderated_by = moderator_id
    sug.moderated_at = datetime.now(timezone.utc)
    sug.moderation_note = (note or "")[:255] or None


def pending_suggestions(campus_id: str | None = None, *, limit: int = 100):
    stmt = select(LocationSuggestion).where(LocationSuggestion.status == "pending")
    if campus_id:
        stmt = stmt.where(LocationSuggestion.campus_id == campus_id)
    stmt = stmt.order_by(LocationSuggestion.created_at.desc()).limit(limit)
    return db.session.execute(stmt).scalars().all()