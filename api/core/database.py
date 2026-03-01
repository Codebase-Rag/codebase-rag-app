from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from codebase_rag.config import settings


class Base(DeclarativeBase):
    pass


DATABASE_URL = (
    f"postgresql://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    """Create all tables if they don't exist."""
    import models.session  # noqa: F401 — ensure models are registered on Base
    Base.metadata.create_all(bind=engine)
