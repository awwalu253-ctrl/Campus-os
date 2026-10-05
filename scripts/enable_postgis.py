"""Idempotently enable PostGIS on the target database."""
from app import create_app
from app.extensions import db
from sqlalchemy import text


def main():
    app = create_app()
    with app.app_context():
        db.session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        db.session.commit()
        print("PostGIS enabled.")


if __name__ == "__main__":
    main()