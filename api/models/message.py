from typing import Literal
from typing_extensions import LiteralString, ParamSpec, TypedDict
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from datetime import datetime

class Message(TypedDict):
    __tablename__ = "messages"

    id = Column(Integer(), primary_key=True)
    session_id = Column(Integer(), ForeignKey("chat_sessions.id"))
    type = Column(String(100), nullable=False)
    timestamp = Column(DateTime(), default=datetime.now)
    content = Column(JSONB)
    chat_session = relationship("ChatSession", back_populates="messages")