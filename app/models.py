from sqlalchemy import Boolean, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase): pass


class LoginSession(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[str] = mapped_column(String(40))


class LoginAttempt(Base):
    __tablename__ = "login_attempts"
    id: Mapped[int] = mapped_column(primary_key=True)
    ip: Mapped[str] = mapped_column(String(64), index=True)
    at: Mapped[str] = mapped_column(String(40))


class Fixture(Base):
    __tablename__ = "fixtures"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    competition: Mapped[str] = mapped_column(String(20), index=True)
    home: Mapped[str] = mapped_column(String(160))
    away: Mapped[str] = mapped_column(String(160))
    kickoff: Mapped[str] = mapped_column(String(40), index=True)
    fetched_at: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(60))
    hg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ag: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Result(Base):
    __tablename__ = "results"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    competition: Mapped[str] = mapped_column(String(20), index=True)
    home: Mapped[str] = mapped_column(String(160))
    away: Mapped[str] = mapped_column(String(160))
    date: Mapped[str] = mapped_column(String(10), index=True)
    hg: Mapped[int] = mapped_column(Integer)
    ag: Mapped[int] = mapped_column(Integer)
    revision: Mapped[str] = mapped_column(String(160))


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    competition: Mapped[str] = mapped_column(String(20), index=True)
    created_at: Mapped[str] = mapped_column(String(40))
    parameters: Mapped[dict] = mapped_column(JSON)
    validation: Mapped[dict] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=False)


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    fixture_id: Mapped[str] = mapped_column(String(100), index=True)
    market: Mapped[str] = mapped_column(String(32))
    model_id: Mapped[str] = mapped_column(String(64))
    probability: Mapped[float] = mapped_column(Float)
    raw_probability: Mapped[float] = mapped_column(Float)
    created_at: Mapped[str] = mapped_column(String(40))
    snapshot: Mapped[dict] = mapped_column(JSON)
    valid: Mapped[bool] = mapped_column(Boolean, default=True)
    won: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class Audit(Base):
    __tablename__ = "audit"
    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    at: Mapped[str] = mapped_column(String(40))
    detail: Mapped[dict] = mapped_column(JSON)


class AppSetting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)


class JobLock(Base):
    __tablename__ = "job_locks"
    name: Mapped[str] = mapped_column(String(40), primary_key=True)
    expires_at: Mapped[str] = mapped_column(String(40))


class Odds(Base):
    __tablename__ = "odds"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    fixture_id: Mapped[str] = mapped_column(String(100), index=True)
    market: Mapped[str] = mapped_column(String(32))
    price: Mapped[float] = mapped_column(Float)
    bookmaker: Mapped[str] = mapped_column(String(100))
    captured_at: Mapped[str] = mapped_column(String(40))
    region: Mapped[str] = mapped_column(String(20))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
