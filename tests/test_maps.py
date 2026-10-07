import uuid

import pytest
from sqlalchemy import event

from app.extensions import db
from app.maps import services as map_services
from app.models import University, Campus
from app.maps.models import Location


@pytest.fixture
def seeded_campus(app):
    """Create a unique test university + campus + 5 approved locations."""
    with app.app_context():
        suffix = uuid.uuid4().hex[:8]
        uni = University(
            slug=f"test-{suffix}",
            name=f"Test University {suffix}",
            short_name=f"TU{suffix}",
        )
        db.session.add(uni)
        db.session.flush()

        campus = Campus(
            university_id=uni.id,
            slug="main",
            name="Main Campus",
        )
        db.session.add(campus)
        db.session.flush()

        for i in range(5):
            db.session.add(Location(
                campus_id=campus.id,
                name=f"Location {i}",
                category="building",
                point=f"SRID=4326;POINT({4.67 + i * 0.0001} {8.48 + i * 0.0001})",
                status="approved",
                source="admin",
            ))
        db.session.commit()
        yield campus.id, 5
        db.session.rollback()


def test_approved_locations_geo_single_query(app, seeded_campus):
    """The N+1 fix must issue exactly ONE SELECT regardless of row count."""
    campus_id, expected_count = seeded_campus

    with app.app_context():
        engine = db.engine
        statements = []

        def _record(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", _record)
        try:
            results = map_services.approved_locations_geo(campus_id)
        finally:
            event.remove(engine, "before_cursor_execute", _record)

        selects = [s for s in statements if s.strip().upper().startswith("SELECT")]
        assert len(selects) == 1, (
            f"expected exactly 1 SELECT, got {len(selects)}:\n" + "\n".join(selects)
        )
        assert len(results) == expected_count
        for row in results:
            assert set(row.keys()) >= {
                "id", "name", "category", "description",
                "lat", "lng", "opening_hours", "phone",
            }
            assert row["lat"] is not None
            assert row["lng"] is not None