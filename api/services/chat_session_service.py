from typing import List, Optional
from sqlalchemy.orm import Session
from models.chat_session import ChatSession


class ChatSessionService:
    """Service for ChatSession CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    def get(self, id: int) -> Optional[ChatSession]:
        return self.db.query(ChatSession).filter(ChatSession.id == id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[ChatSession]:
        return self.db.query(ChatSession).offset(skip).limit(limit).all()

    def create(self, data: dict) -> ChatSession:
        session = ChatSession(**data)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def update(self, id: int, data: dict) -> Optional[ChatSession]:
        session = self.get(id)
        if session:
            for key, value in data.items():
                setattr(session, key, value)
            self.db.commit()
            self.db.refresh(session)
        return session

    def delete(self, id: int) -> bool:
        session = self.get(id)
        if session:
            self.db.delete(session)
            self.db.commit()
            return True
        return False

    def get_by_workspace(self, workspace: str) -> List[ChatSession]:
        return self.db.query(ChatSession).filter(ChatSession.workspace == workspace).all()

    def get_recent(self, limit: int = 10) -> List[ChatSession]:
        return (
            self.db.query(ChatSession)
            .order_by(ChatSession.updated_on.desc())
            .limit(limit)
            .all()
        )
