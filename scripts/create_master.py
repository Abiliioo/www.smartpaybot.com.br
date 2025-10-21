# scripts/create_master.py
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from infrastructure.db import SessionLocal
from domain.models import User
from sqlalchemy import select
from werkzeug.security import generate_password_hash

def main():
    with SessionLocal() as db:
        exists = db.execute(select(User).where(User.username == "adm")).scalar_one_or_none()
        if exists:
            print("Usuário 'adm' já existe -> id:", exists.id)
            return

        u = User(
            username="adm",
            email="adm@teste.com.br",
            phone="11948038992",
            password_hash=generate_password_hash("MinhaSenha123!"),
            is_admin=True,
            is_subscriber=True,
            chat_id="5933529541",     # Telegram ID
        )
        db.add(u)
        db.commit()
        print("Usuário master criado -> id:", u.id)

if __name__ == "__main__":
    main()
