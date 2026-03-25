"""
Background Worker for Session Sync

Manages the background task that syncs Redis sessions to PostgreSQL.
This module provides utilities to start, stop, and manage the sync worker.
"""

import asyncio
import logging
from typing import Optional
from contextlib import asynccontextmanager

from services.session_sync_service import SessionSyncService, get_sync_service, sync_on_shutdown

logger = logging.getLogger(__name__)


class SessionSyncWorker:
    """
    Manages the background session sync worker.
    
    This worker runs a periodic sync task that ensures all Redis sessions
    are backed up to PostgreSQL according to the configured interval.
    """

    def __init__(self, sync_interval: int = 300):
        """
        Initialize the worker.
        
        Args:
            sync_interval: Time in seconds between sync operations (default: 5 minutes)
        """
        self.sync_interval = sync_interval
        self.sync_service = get_sync_service(sync_interval)
        self.sync_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """
        Start the background sync worker task.
        
        This creates an asyncio task that runs the periodic sync loop.
        Call during application startup.
        """
        if self.sync_task is not None:
            logger.warning("Sync worker already running")
            return

        logger.info(f"Starting session sync worker (sync_interval={self.sync_interval}s)")
        
        try:
            self.sync_task = asyncio.create_task(self.sync_service.start())
            logger.info("Session sync worker started successfully")
        except Exception as e:
            logger.error(f"Failed to start sync worker: {e}", exc_info=True)
            raise

    async def stop(self) -> None:
        """
        Stop the background sync worker task.
        
        Performs a final sync before stopping.
        Call during application shutdown.
        """
        logger.info("Stopping session sync worker")
        
        try:
            # Stop the main sync loop
            await self.sync_service.stop()
            
            # Wait for the task to complete
            if self.sync_task:
                await asyncio.wait_for(self.sync_task, timeout=5.0)
                self.sync_task = None
            
            # Perform final sync
            logger.info("Performing final sync before shutdown")
            await sync_on_shutdown()
            
            logger.info("Session sync worker stopped successfully")
        except asyncio.TimeoutError:
            logger.warning("Sync worker task timeout during shutdown")
            if self.sync_task:
                self.sync_task.cancel()
                self.sync_task = None
        except Exception as e:
            logger.error(f"Error stopping sync worker: {e}", exc_info=True)

    async def force_sync(self, session_id: str) -> bool:
        """
        Force an immediate sync of a specific session.
        
        Useful for critical operations that need guaranteed persistence.
        
        Args:
            session_id: The session ID to sync
            
        Returns:
            True if sync was successful
        """
        return await self.sync_service.force_sync_session(session_id)

    async def force_sync_all(self) -> int:
        """
        Force an immediate sync of all sessions.
        
        Returns:
            Number of sessions synced
        """
        return await self.sync_service.force_sync_all()

    def is_running(self) -> bool:
        """Check if the sync worker is currently running."""
        return self.sync_task is not None and not self.sync_task.done()


# Global worker instance
_worker: Optional[SessionSyncWorker] = None


def get_worker(sync_interval: int = 300) -> SessionSyncWorker:
    """Get or create the global sync worker instance."""
    global _worker
    if _worker is None:
        _worker = SessionSyncWorker(sync_interval)
    return _worker


@asynccontextmanager
async def managed_sync_worker(sync_interval: int = 300):
    """
    Context manager for the sync worker.
    
    Usage:
        async with managed_sync_worker(sync_interval=300) as worker:
            # worker is running
            await worker.force_sync(session_id)
            # worker stops here automatically
    
    Args:
        sync_interval: Time in seconds between syncs
    """
    worker = SessionSyncWorker(sync_interval)
    await worker.start()
    try:
        yield worker
    finally:
        await worker.stop()
