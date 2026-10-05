"""Celery tasks for Pulse.

Celery is initialized in app/extensions/__init__.py via `celery_app.py` if you
have one, otherwise in tasks/celery_app.py. Here we just register tasks on
whatever Celery instance is available.
"""
from celery import shared_task


@shared_task(name="pulse.sweep_expired")
def sweep_expired_task():
    # Import inside the task to avoid circular import at module load
    from app import create_app
    from app.pulse import services

    app = create_app()
    with app.app_context():
        result = services.sweep_expired()
        return result