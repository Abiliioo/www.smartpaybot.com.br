# scripts/dump_users.py
from __future__ import annotations
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from infrastructure.config import get_settings
from infrastructure.db import SessionLocal, init_db
from domain.models import User

if __name__ == "__main__":
    settings = get_settings()
    print(f"DB URL: {settings.DATABASE_URL}")
    init_db(create_all=False)
    with SessionLocal() as db:
        users = db.query(User).order_by(User.id.asc()).all()
        if not users:
            print("(sem usuários)")
        else:
            for u in users:
                print(f"id={u.id} username={u.username} email={u.email} chat_id={u.chat_id}")
