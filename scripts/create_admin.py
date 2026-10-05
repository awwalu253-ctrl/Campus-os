"""Create the first platform admin.

Usage:
    FLASK_ENV=development flask shell < scripts/create_admin.py
or:
    python -m scripts.create_admin you@example.com "Your Name"
"""
import sys
from app import create_app
from app.extensions import db
from app.models import User, TrustScore
from app.core.security import hash_password


def main(email: str, name: str, password: str | None = None):
    app = create_app()
    with app.app_context():
        if User.query.filter_by(email=email.lower()).first():
            print(f"User {email} already exists.")
            return
        pwd = password or input("Password: ")
        user = User(
            email=email.lower(),
            display_name=name,
            password_hash=hash_password(pwd),
            role="platform_admin",
            status="active",
        )
        user.trust = TrustScore()
        db.session.add(user)
        db.session.commit()
        print(f"Created platform admin {email} (id={user.id})")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.create_admin <email> <name> [password]")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)