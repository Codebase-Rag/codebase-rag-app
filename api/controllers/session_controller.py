from fastapi import APIRouter
from services.session_service import get_all_sessions

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/")
def list_sessions():
    return get_all_sessions()