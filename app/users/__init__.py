from app.extensions import db, login_manager
from app.models import User


@login_manager.user_loader
def load_user(user_id: str):
    return db.session.get(User, user_id)