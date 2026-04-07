import pickle
from pydantic_ai.messages import ModelMessage, ModelMessagesTypeAdapter

from models import Message, ChatSession
from prompts.summary_agent_prompt import USER_PROMPT
from agents.summary_agent import summary_agent
from core.db.database import redis_client, SessionLocal
from celery_app.main import celery
from services.chat_session_service import ChatSessionService
from services.message_service import MessageService

def _deserialize_message(content: dict | list) -> ModelMessage:
    """Convert stored dict back to ModelRequest or ModelResponse using TypeAdapter."""
    # Content is stored as a list with single message for proper type handling
    if isinstance(content, list):
        messages = ModelMessagesTypeAdapter.validate_python(content)
        return messages[0] if messages else None
    # Legacy format - wrap in list
    messages = ModelMessagesTypeAdapter.validate_python([content])
    return messages[0] if messages else None

@celery.task(max_retries=3, default_retry_delay=30)
def sync_session_to_db(): 
    with SessionLocal() as db:
        session_service = ChatSessionService(db)
        message_service = MessageService(db)
        for key in redis_client.scan_iter():
            session_id = key.decode() if isinstance(key, bytes) else key
            history = pickle.loads(redis_client.get(key))
            if not history:
                continue
            session = session_service.get(session_id)
            if session is None:
                session_service.create({
                    "id": session_id, 
                    "summary": "", 
                    "created_on": history[0].timestamp, 
                    "updated_on": history[-1].timestamp, 
                })
            is_updated = False
            for message in history:
                if message_service.get(message.id) is None:
                    is_updated = True
                    message_service.create({
                        "id": message.id, 
                        "session_id": session_id, 
                        "type": message.type, 
                        "timestamp": message.timestamp, 
                        "content": message.content, 
                    })
            if is_updated:
                summary = summary_agent.run_sync(user_prompt=USER_PROMPT, message_history=[_deserialize_message(msg.content) for msg in history]).output
                session_service.update(id=session_id, data={
                    "summary": summary, 
                    "updated_on": history[-1].timestamp, 
                })

    print("database sync complete!")