"""Celery entrypoint:  celery -A tasks.celery_app.celery worker -l info"""
import os
from celery import Celery

# Ensure FLASK_ENV is production on Render
os.environ.setdefault("FLASK_ENV", "production")

from app import create_app

flask_app = create_app()

celery = Celery(
    "campus_os",
    broker=flask_app.config["CELERY_BROKER_URL"],
    backend=flask_app.config["CELERY_RESULT_BACKEND"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    beat_schedule={
        "sweep-expired-reports": {
            "task": "pulse.sweep_expired",
            "schedule": 300.0,
        },
    },
)

from app.pulse import tasks as _pulse_tasks  # noqa: E402,F401