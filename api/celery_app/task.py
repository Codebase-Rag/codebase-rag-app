import pickle

from models import Message, ChatSession
from core.db.database import redis_client, SessionLocal
from celery_app.main import celery

@celery.task(max_retries=3, default_retry_delay=30)
def sync_session_to_db(): 
    with SessionLocal() as db:
        for key in redis_client.scan_iter():
            session_id = key.decode() if isinstance(key, bytes) else key
            history = pickle.loads(redis_client.get(key))
            if not history:
                continue
            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            if session is None:
                session = ChatSession(
                    id=session_id,
                    summary="",
                    created_on=history[0].timestamp, 
                    updated_on=history[-1].timestamp, 
                )
                db.add(session)
                db.commit()
                db.refresh(session)
            for message in history:
                if db.query(Message).filter(Message.id == message.id).first() is None:
                    db.add(message)
            db.commit()
    print("database sync complete!")