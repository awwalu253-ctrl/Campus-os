"""Production entrypoint used by Gunicorn on Render."""
from app import create_app

app = create_app()