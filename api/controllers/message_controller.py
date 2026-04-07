from fastapi import APIRouter
from services.message_service import MessageService
from core.db.database import SessionLocal

router = APIRouter(prefix="/messages", tags=["messages"])

@router.get("/")
def list_messages():
    with SessionLocal() as db:
        message_service = MessageService(db)
        return message_service.get_all()

@router.get("/{session_id}")
def get_messages_by_session(session_id: str):
    with SessionLocal() as db:
        message_service = MessageService(db)
        return message_service.get_by_session(session_id)