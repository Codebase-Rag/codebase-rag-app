from typing import List, Optional
from sqlalchemy.orm import Session
from models.message import Message


class MessageService:
    """Service for Message CRUD operations."""

    def __init__(self, db: Session):
        self.db = db

    def get(self, id: int) -> Optional[Message]:
        return self.db.query(Message).filter(Message.id == id).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Message]:
        return self.db.query(Message).offset(skip).limit(limit).all()

    def create(self, data: dict) -> Message:
        message = Message(**data)
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def update(self, id: int, data: dict) -> Optional[Message]:
        message = self.get(id)
        if message:
            for key, value in data.items():
                setattr(message, key, value)
            self.db.commit()
            self.db.refresh(message)
        return message

    def delete(self, id: int) -> bool:
        message = self.get(id)
        if message:
            self.db.delete(message)
            self.db.commit()
            return True
        return False

    def get_by_session(self, session_id: int) -> List[Message]:
        return (
            self.db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.timestamp.asc())
            .all()
        )

    def get_by_session_and_type(self, session_id: int, message_type: str) -> List[Message]:
        return (
            self.db.query(Message)
            .filter(Message.session_id == session_id, Message.type == message_type)
            .all()
        )

    def delete_by_session(self, session_id: int) -> int:
        """Delete all messages for a session. Returns count of deleted messages."""
        count = self.db.query(Message).filter(Message.session_id == session_id).delete()
        self.db.commit()
        return count
