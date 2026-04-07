import uuid
from typing import Literal
from typing_extensions import LiteralString, ParamSpec, TypedDict
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from datetime import datetime

from core.db.models import Base

class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    type = Column(String(100), nullable=False)
    timestamp = Column(DateTime(), default=datetime.now)
    content = Column(JSONB)
    chat_session = relationship("ChatSession", back_populates="message")