import pickle
from typing import Any

from sqlalchemy import Column, String, DateTime, Text, func
from pydantic_ai.messages import ModelMessagesTypeAdapter
from core.db.database import redis_client
from core.db.database import SessionLocal, Base


class Session(Base):
    __tablename__ = "sessions"
    session_id = Column(String, primary_key=True)
    # workspace = Column(String)
    history = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @staticmethod
    def get_all() -> list[dict]:
        """Get all sessions with session_id and created_at from Postgres."""
        with SessionLocal() as db:
            rows = db.query(Session.session_id, Session.created_at).all()
            return [
                {"session_id": row.session_id, "created_at": row.created_at.isoformat()}
                for row in rows
            ]

    @staticmethod
    def get(session_id: str) -> list[Any]:
        """Load session history. Checks Redis cache first, falls back to Postgres."""
        # Try Redis cache first
        cached = redis_client.get(session_id)
        if cached is not None:
            return pickle.loads(cached)

        # Fall back to Postgres
        with SessionLocal() as db:
            row = db.query(Session).filter(Session.session_id == session_id).first()
            if row is None:
                return []
            history = list(ModelMessagesTypeAdapter.validate_json(row.history))
            # Re-populate Redis cache
            redis_client.set(session_id, pickle.dumps(history))
            return history

    @staticmethod
    def set(session_id: str, history: list[Any]) -> None:
        """Persist session history to Postgres and update Redis cache."""
        history_json = ModelMessagesTypeAdapter.dump_json(history).decode()

        with SessionLocal() as db:
            row = db.query(Session).filter(Session.session_id == session_id).first()
            if row is None:
                row = Session(session_id=session_id, history=history_json)
                db.add(row)
            else:
                row.history = history_json
            db.commit()

        # Update Redis cache
        redis_client.set(session_id, pickle.dumps(history))

    @staticmethod
    def delete(session_id: str) -> None:
        """Delete a session from both Postgres and Redis."""
        with SessionLocal() as db:
            db.query(Session).filter(Session.session_id == session_id).delete()
            db.commit()
        redis_client.delete(session_id)
