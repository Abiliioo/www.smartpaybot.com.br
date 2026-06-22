# domain/models.py
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Index,
    func,
    BigInteger,
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from infrastructure.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(150), nullable=False, unique=True, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Armazenar sempre HASH aqui (hash/verify será tratado na camada de auth)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_subscriber: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    bot_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="1")

    chat_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    telegram_link_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relacionamentos
    keywords: Mapped[list["UserKeyword"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    user_projects: Mapped[list["ProjectPerUser"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    subscription: Mapped[Optional["Subscription"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r}>"


class UserKeyword(Base):
    __tablename__ = "user_keywords"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    keyword: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user: Mapped["User"] = relationship(back_populates="keywords")

    __table_args__ = (
        UniqueConstraint("user_id", "keyword", name="uq_user_keyword"),
        Index("ix_user_keywords_keyword", "keyword"),
    )

    def __repr__(self) -> str:
        return f"<UserKeyword user_id={self.user_id} keyword={self.keyword!r}>"


class ProjectGlobal(Base):
    """
    Projetos coletados globalmente pelo crawler, deduplicados por project_id (ID numérico da URL).
    O link e o título podem mudar ao longo do tempo; guardamos o último conhecido.
    """
    __tablename__ = "projects_global"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    # Novo identificador canônico (único) extraído da URL (ex.: 689946)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)

    title: Mapped[str] = mapped_column(Text, nullable=False)
    link: Mapped[str] = mapped_column(String(512), nullable=False, index=True)  # não é mais unique

    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Metadados ricos coletados pelo scraper local (ausentes em registros antigos → None)
    category: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    level: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    proposals: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    interested: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    client_rating: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    client_reviews: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    user_projects: Mapped[list["ProjectPerUser"]] = relationship(
        back_populates="global_project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<ProjectGlobal id={self.id} project_id={self.project_id} link={self.link!r}>"


class ProjectPerUser(Base):
    """
    Projeção por usuário: o mesmo projeto global pode aparecer para vários usuários,
    mas NUNCA duplicado para o mesmo (user_id, global_project_id).
    Mantemos um snapshot de title/link para fins de notificação/histórico.
    """
    __tablename__ = "projects_per_user"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    global_project_id: Mapped[int] = mapped_column(
        ForeignKey("projects_global.id", ondelete="CASCADE"), nullable=False, index=True
    )

    link: Mapped[str] = mapped_column(String(512), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    matched_keyword: Mapped[str] = mapped_column(String(50), nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notify_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    won: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    won_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    won_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="user_projects")
    global_project: Mapped["ProjectGlobal"] = relationship(back_populates="user_projects")

    __table_args__ = (
        # troca a unicidade baseada em link por (user_id, global_project_id)
        UniqueConstraint("user_id", "global_project_id", name="uq_user_global_project"),
        Index("ix_user_project_created_at", "user_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ProjectPerUser id={self.id} user_id={self.user_id} "
            f"global_project_id={self.global_project_id} link={self.link!r}>"
        )


class Plan(Base):
    """
    Catálogo de planos disponíveis (Free, Pro, …).
    max_keywords = -1  → ilimitado
    max_alerts_day = -1 → ilimitado
    """
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    max_keywords: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    max_alerts_day: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="plan")

    def __repr__(self) -> str:
        return f"<Plan slug={self.slug!r} max_kw={self.max_keywords} max_alerts={self.max_alerts_day}>"


class Subscription(Base):
    """
    Uma assinatura por usuário (UNIQUE user_id).
    status: 'active' | 'canceled' | 'trialing'
    Sem registro = plano Free implícito.
    """
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    plan_id: Mapped[int] = mapped_column(
        ForeignKey("plans.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    # reservado para integração futura com Stripe
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="subscription")
    plan: Mapped["Plan"] = relationship(back_populates="subscriptions")

    def __repr__(self) -> str:
        return f"<Subscription user_id={self.user_id} plan_id={self.plan_id} status={self.status!r}>"


class UserAlertDaily(Base):
    """
    Contador diário de alertas enviados por usuário.
    Usado para enforçar o limite do plano Free (max_alerts_day).
    """
    __tablename__ = "user_alerts_daily"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False)
    alerts_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_alert_daily"),
    )

    def __repr__(self) -> str:
        return f"<UserAlertDaily user_id={self.user_id} date={self.date} sent={self.alerts_sent}>"
