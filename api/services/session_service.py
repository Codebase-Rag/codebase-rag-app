from core.db.database import redis_client, SessionLocal
from services.message_service import MessageService
from models import Message

import asyncio
import pickle

class SessionService:

    def _get_session_sync(self, session_id: str) -> list[Message]:
        session = redis_client.get(session_id)
        if session != None:
            return pickle.loads(session)
        with SessionLocal() as db:
            message_service = MessageService(db)
            return message_service.get_by_session(session_id)

    SESSION_TTL_SECONDS = 86400  # 1 day

    def _update_session_sync(self, session_id: str, messages: list[Message]):
        redis_client.set(session_id, pickle.dumps(messages), ex=self.SESSION_TTL_SECONDS)

    async def get_session(self, session_id: str) -> list[Message]:
        return await asyncio.to_thread(self._get_session_sync, session_id)
        
    async def update_session(self, session_id: str, messages: list[Message]):
        await asyncio.to_thread(self._update_session_sync, session_id, messages)