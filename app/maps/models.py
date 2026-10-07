from geoalchemy2 import Geometry
from sqlalchemy import func as sa_func

from app.extensions import db
from ..models.mixins import UUIDMixin, TimestampMixin


LOCATION_STATUS = ("approved", "pending", "rejected")


class Location(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "locations"

    campus_id = db.Column(db.String(36), db.ForeignKey("campuses.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(32), nullable=False, index=True)
    description = db.Column(db.String(500), nullable=True)

    # PostGIS point (SRID 4326 = WGS84).
    # spatial_index=False prevents GeoAlchemy2 from creating its own
    # implicit GiST index; we declare the one we want explicitly below.
    point = db.Column(
        Geometry(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=False,
    )

    # PostGIS polygon (optional, for campus boundaries and large buildings).
    polygon = db.Column(
        Geometry(geometry_type="POLYGON", srid=4326, spatial_index=False),
        nullable=True,
    )

    opening_hours = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(32), nullable=True)

    source = db.Column(db.String(16), nullable=False, default="student")
    status = db.Column(db.String(16), nullable=False, default="approved", index=True)

    created_by = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"),
                           nullable=True)
    verified_by = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"),
                            nullable=True)
    verified_at = db.Column(db.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        db.Index("ix_locations_campus_status", "campus_id", "status"),
        db.Index("ix_locations_point_gist", "point", postgresql_using="gist"),
    )


class LocationSuggestion(UUIDMixin, TimestampMixin, db.Model):
    __tablename__ = "location_suggestions"

    campus_id = db.Column(db.String(36), db.ForeignKey("campuses.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    proposed_by = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"),
                            nullable=True, index=True)

    name = db.Column(db.String(160), nullable=False)
    category = db.Column(db.String(32), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    lat = db.Column(db.Float, nullable=False)
    lng = db.Column(db.Float, nullable=False)

    status = db.Column(db.String(16), nullable=False, default="pending", index=True)
    # pending | approved | rejected

    moderated_by = db.Column(db.String(36), db.ForeignKey("users.id", ondelete="SET NULL"),
                             nullable=True)
    moderated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    moderation_note = db.Column(db.String(255), nullable=True)

    # When approved, we create a Location and link back
    approved_location_id = db.Column(db.String(36),
                                     db.ForeignKey("locations.id", ondelete="SET NULL"),
                                     nullable=True)