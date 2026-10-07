import os

import pytest
from sqlalchemy import text

from app import create_app
from app.extensions import db as _db


@pytest.fixture()
def app():
    os.environ["FLASK_ENV"] = "testing"
    app = create_app("testing")
    with app.app_context():
        _db.session.execute(text("CREATE EXTENSION IF NOT EXISTS postgis;"))
        _db.session.commit()
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _clean(app):
    yield
    _db.session.rollback()