from app import create_app
from app.extensions import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    rows = db.session.execute(
        text(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_name = 'campuses' "
            "ORDER BY ordinal_position"
        )
    ).all()
    for row in rows:
        print(f"{row[0]:20s} {row[1]:20s} nullable={row[2]}")