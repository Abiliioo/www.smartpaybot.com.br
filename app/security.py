# app/security.py
from __future__ import annotations
from flask_login import UserMixin

class AppUser(UserMixin):
    def __init__(self, user_id: int, username: str, is_admin: bool = False, theme_preference: str = "dark"):
        # Flask-Login exige id como string serializável
        self.id = str(user_id)
        self.username = username
        self.is_admin = is_admin
        self.theme_preference = theme_preference

    @staticmethod
    def from_domain(user) -> "AppUser":
        return AppUser(user.id, user.username, user.is_admin, user.theme_preference)
