# scripts/seed_plans.py
"""
Popula a tabela 'plans' com os planos Free e Pro.
Idempotente — seguro rodar múltiplas vezes.

Uso:
    python scripts/seed_plans.py
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from infrastructure.db import SessionLocal, init_db
from domain.models import Plan
from sqlalchemy import select

PLANS = [
    {
        "slug": "free",
        "name": "Gratuito",
        "max_keywords": 3,
        "max_alerts_day": 10,
        "is_active": True,
    },
    {
        "slug": "pro",
        "name": "Pro",
        "max_keywords": -1,   # ilimitado
        "max_alerts_day": -1, # ilimitado
        "is_active": True,
    },
]


def seed() -> None:
    init_db(create_all=True)

    with SessionLocal() as db:
        for data in PLANS:
            existing = db.execute(
                select(Plan).where(Plan.slug == data["slug"])
            ).scalar_one_or_none()

            if existing:
                # Atualiza limites caso tenham mudado
                existing.name = data["name"]
                existing.max_keywords = data["max_keywords"]
                existing.max_alerts_day = data["max_alerts_day"]
                existing.is_active = data["is_active"]
                db.add(existing)
                print(f"  [seed] plano '{data['slug']}' atualizado.")
            else:
                db.add(Plan(**data))
                print(f"  [seed] plano '{data['slug']}' criado.")

        db.commit()
    print("[seed] Concluído.")


if __name__ == "__main__":
    seed()
