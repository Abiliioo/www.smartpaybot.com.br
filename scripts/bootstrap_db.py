# scripts/bootstrap_db.py
from __future__ import annotations

# 1) Ajuste do sys.path ANTES de qualquer import do projeto
import os, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 2) Agora podemos importar módulos do projeto
from werkzeug.security import generate_password_hash
from infrastructure.db import SessionLocal, init_db
from infrastructure.config import get_settings
from domain.models import User

def set_password(username: str, new_password: str) -> None:
    with SessionLocal() as db:
        u = db.query(User).filter(User.username == username).first()
        if not u:
            print(f"Usuário '{username}' não encontrado.")
            return
        u.password_hash = generate_password_hash(new_password)
        db.add(u)
        db.commit()
        print(f"Senha de '{username}' atualizada com sucesso.")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Uso: python scripts/bootstrap_db.py <username> <nova_senha>")
        sys.exit(1)

    settings = get_settings()
    print(f"DB URL: {settings.DATABASE_URL}")  # mostra qual banco está usando
    init_db(create_all=False)  # só inicializa engine/metadados; sem criar tabelas

    set_password(sys.argv[1], sys.argv[2])
