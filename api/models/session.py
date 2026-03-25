import pickle
import logging
from typing import Any

from sqlalchemy import Column, String, DateTime, Text, func
from pydantic_ai.messages import ModelMessagesTypeAdapter
from core.redis import redis_client
from core.database import SessionLocal, Base

logger = logging.getLogger(__name__)


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
        """
        Get all sessions with session_id and created_at from Postgres.
        Postgres is the source of truth for session listings.
        """
        with SessionLocal() as db:
            rows = db.query(Session.session_id, Session.created_at).all()
            return [
                {"session_id": row.session_id, "created_at": row.created_at.isoformat()}
                for row in rows
            ]

    @staticmethod
    def get(session_id: str) -> list[Any]:
        """
        Load session history from Redis (primary store).
        Falls back to Postgres only on first access, then caches in Redis.
        
        Priority:
        1. Redis (hot cache - fastest)
        2. Postgres (cold storage - fallback)
        3. Empty list (new session)
        """
        # Try Redis cache first (primary store)
        cached = redis_client.get(session_id)
        if cached is not None:
            return pickle.loads(cached)

        # Fall back to Postgres (cold storage restoration)
        logger.debug(f"Session {session_id} not in Redis, checking Postgres")
        with SessionLocal() as db:
            row = db.query(Session).filter(Session.session_id == session_id).first()
            if row is None:
                logger.debug(f"Session {session_id} not found anywhere - new session")
                return []
            
            history = list(ModelMessagesTypeAdapter.validate_json(row.history))
            logger.debug(f"Restored session {session_id} from Postgres to Redis cache")
            
            # Re-populate Redis cache for future access
            redis_client.set(session_id, pickle.dumps(history))
            return history

    @staticmethod
    def set(session_id: str, history: list[Any]) -> None:
        """
        Update session history in Redis only (non-blocking, fast path).
        Background sync service handles async persistence to Postgres.
        
        This keeps the request path fast by only writing to Redis.
        The sync service will periodically sync to Postgres for durability.
        """
        try:
            # Write only to Redis (fire and forget - non-blocking)
            redis_client.set(session_id, pickle.dumps(history))
            logger.debug(f"Session {session_id} updated in Redis (queued for Postgres sync)")
        except Exception as e:
            logger.error(f"Failed to update session {session_id} in Redis: {e}")
            raise

    @staticmethod
    def set_with_immediate_sync(session_id: str, history: list[Any]) -> None:
        """
        Update session history in Redis AND immediately sync to Postgres.
        Use this for critical operations that need guaranteed persistence.
        
        Note: This blocks and is slower than set(). Prefer set() for normal
        operations and let the background sync handle eventual consistency.
        
        Args:
            session_id: The session ID
            history: The session history to store
        """
        history_json = ModelMessagesTypeAdapter.dump_json(history).decode()

        # Update Postgres (blocking write for guaranteed persistence)
        with SessionLocal() as db:
            row = db.query(Session).filter(Session.session_id == session_id).first()
            if row is None:
                row = Session(session_id=session_id, history=history_json)
                db.add(row)
            else:
                row.history = history_json
            db.commit()

        # Update Redis cache (should be fast)
        redis_client.set(session_id, pickle.dumps(history))
        logger.debug(f"Session {session_id} synced to both Redis and Postgres")

    @staticmethod
    def delete(session_id: str) -> None:
        """
        Delete a session from both Redis and Postgres.
        This is a critical operation that should be properly persisted.
        """
        # Delete from Redis first
        redis_client.delete(session_id)
        
        # Delete from Postgres (ensure immediate persistence)
        with SessionLocal() as db:
            db.query(Session).filter(Session.session_id == session_id).delete()
            db.commit()
        
        logger.debug(f"Session {session_id} deleted from Redis and Postgres")
