"""
Session Sync Service

Handles periodic synchronization of Redis session data to PostgreSQL.
Runs as a background task to keep the persistent store updated.
"""

import pickle
import asyncio
import logging
from typing import List, Optional
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from pydantic_ai.messages import ModelMessagesTypeAdapter
from core.redis import redis_client
from core.database import SessionLocal
from models.session import Session

logger = logging.getLogger(__name__)


class SessionSyncService:
    """Service for syncing Redis sessions to PostgreSQL."""

    def __init__(self, sync_interval: int = 300):
        """
        Initialize the sync service.

        Args:
            sync_interval: Interval in seconds between syncs (default: 300s = 5 minutes)
        """
        self.sync_interval = sync_interval
        self.is_running = False

    async def start(self) -> None:
        """Start the background sync worker."""
        if self.is_running:
            logger.warning("Sync service already running")
            return

        self.is_running = True
        logger.info(f"Starting session sync service (interval: {self.sync_interval}s)")

        try:
            while self.is_running:
                await asyncio.sleep(self.sync_interval)
                await self.sync_sessions()
        except asyncio.CancelledError:
            logger.info("Sync service stopped")
            self.is_running = False
        except Exception as e:
            logger.error(f"Sync service error: {e}", exc_info=True)
            self.is_running = False

    async def stop(self) -> None:
        """Stop the background sync worker."""
        logger.info("Stopping session sync service")
        self.is_running = False

    async def sync_sessions(self) -> None:
        """
        Sync all active sessions from Redis to PostgreSQL.
        This runs periodically in the background.
        """
        try:
            session_keys = await self._get_active_session_keys()
            if not session_keys:
                logger.debug("No active sessions to sync")
                return

            logger.debug(f"Syncing {len(session_keys)} sessions to PostgreSQL")

            for session_id in session_keys:
                try:
                    await self._sync_session_to_postgres(session_id)
                except Exception as e:
                    logger.error(f"Failed to sync session {session_id}: {e}")
                    continue

            logger.debug(f"Successfully synced {len(session_keys)} sessions")

        except Exception as e:
            logger.error(f"Error during session sync: {e}", exc_info=True)

    async def _get_active_session_keys(self) -> List[str]:
        """
        Get all active session keys from Redis.

        Returns:
            List of session IDs (Redis keys)
        """
        try:
            keys = redis_client.keys("*")
            return [key.decode() if isinstance(key, bytes) else key for key in keys]
        except Exception as e:
            logger.error(f"Failed to get session keys from Redis: {e}")
            return []

    async def _sync_session_to_postgres(self, session_id: str) -> None:
        """
        Sync a single session from Redis to PostgreSQL.

        Args:
            session_id: The session ID to sync
        """
        try:
            # Get session data from Redis
            cached_data = redis_client.get(session_id)
            if cached_data is None:
                logger.debug(f"Session {session_id} not found in Redis")
                return

            # Deserialize the history
            history = pickle.loads(cached_data)

            # Convert to JSON for storage
            history_json = ModelMessagesTypeAdapter.dump_json(history).decode()

            # Update PostgreSQL
            with SessionLocal() as db:
                row = db.query(Session).filter(
                    Session.session_id == session_id
                ).first()

                if row is None:
                    # Create new session record
                    row = Session(
                        session_id=session_id,
                        history=history_json
                    )
                    db.add(row)
                    logger.debug(f"Created new session record for {session_id}")
                else:
                    # Update existing session record
                    row.history = history_json
                    logger.debug(f"Updated session record for {session_id}")

                db.commit()

        except SQLAlchemyError as e:
            logger.error(f"Database error syncing session {session_id}: {e}")
            raise
        except Exception as e:
            logger.error(f"Error syncing session {session_id}: {e}")
            raise

    async def force_sync_session(self, session_id: str) -> bool:
        """
        Force immediate sync of a single session to PostgreSQL.
        Useful for critical operations that need immediate persistence.

        Args:
            session_id: The session ID to sync

        Returns:
            True if sync was successful, False otherwise
        """
        try:
            await self._sync_session_to_postgres(session_id)
            return True
        except Exception as e:
            logger.error(f"Failed to force sync session {session_id}: {e}")
            return False

    async def force_sync_all(self) -> int:
        """
        Force immediate sync of all sessions.
        Useful for graceful shutdown scenarios.

        Returns:
            Number of sessions successfully synced
        """
        try:
            session_keys = await self._get_active_session_keys()
            synced_count = 0

            for session_id in session_keys:
                try:
                    await self._sync_session_to_postgres(session_id)
                    synced_count += 1
                except Exception as e:
                    logger.error(f"Failed to sync session {session_id} during force_sync_all: {e}")
                    continue

            logger.info(f"Force synced {synced_count}/{len(session_keys)} sessions")
            return synced_count

        except Exception as e:
            logger.error(f"Error during force_sync_all: {e}")
            return 0


# Global instance for easier access
_sync_service: Optional[SessionSyncService] = None


def get_sync_service(sync_interval: int = 300) -> SessionSyncService:
    """Get or create the global sync service instance."""
    global _sync_service
    if _sync_service is None:
        _sync_service = SessionSyncService(sync_interval)
    return _sync_service


async def sync_on_shutdown() -> None:
    """Sync all sessions during graceful shutdown."""
    logger.info("Performing final session sync before shutdown")
    if _sync_service:
        await _sync_service.force_sync_all()
