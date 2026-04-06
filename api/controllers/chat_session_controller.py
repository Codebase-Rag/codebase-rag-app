from fastapi import APIRouter
from services.chat_session_service import ChatSessionService
from core.db.database import SessionLocal

router = APIRouter(prefix="/sessions", tags=["sessions"])

@router.get("/")
def list_sessions():
    with SessionLocal() as db:
        chat_session_service = ChatSessionService(db)
        return chat_session_service.get_all()

