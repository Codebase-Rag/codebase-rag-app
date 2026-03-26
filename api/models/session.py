import base64
import enum
import pickle
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import relationship, selectinload

from pydantic_ai.messages import (
    AudioUrl,
    BinaryContent,
    DocumentUrl,
    ImageUrl,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
    VideoUrl,
    error_details_ta,
    tool_return_ta,
)
from pydantic_ai.usage import Usage

from core.redis import redis_client
from core.database import SessionLocal, Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MessageKind(str, enum.Enum):
    REQUEST = "request"
    RESPONSE = "response"


class PartType(str, enum.Enum):
    SYSTEM_PROMPT = "system_prompt"
    USER_PROMPT = "user_prompt"
    TOOL_RETURN = "tool_return"
    RETRY_PROMPT = "retry_prompt"
    TEXT = "text"
    TOOL_CALL = "tool_call"
    THINKING = "thinking"


class Session(Base):
    __tablename__ = "sessions"

    session_id = Column(String, primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    archived = Column(Boolean, nullable=False, default=False, server_default="false")

    messages = relationship(
        "Message",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="Message.sequence_index",
        passive_deletes=True,
    )

    @staticmethod
    def get_all() -> list[dict]:
        """Get all sessions with session_id and created_at from Postgres."""
        with SessionLocal() as db:
            rows = db.query(Session.session_id, Session.created_at).all()
            return [
                {"session_id": row.session_id, "created_at": row.created_at.isoformat()}
                for row in rows
            ]

    @staticmethod
    def get(session_id: str) -> list[ModelMessage]:
        """Load session history. Checks Redis cache first, falls back to Postgres."""
        cached = redis_client.get(session_id)
        if cached is not None:
            return pickle.loads(cached)

        with SessionLocal() as db:
            messages = (
                db.query(Message)
                .filter(Message.session_id == session_id)
                .order_by(Message.sequence_index)
                .options(
                    selectinload(Message.parts).selectinload(MessagePart.system_prompt),
                    selectinload(Message.parts).selectinload(MessagePart.user_prompt),
                    selectinload(Message.parts).selectinload(MessagePart.tool_return),
                    selectinload(Message.parts).selectinload(MessagePart.retry_prompt),
                    selectinload(Message.parts).selectinload(MessagePart.text_part),
                    selectinload(Message.parts).selectinload(MessagePart.tool_call),
                    selectinload(Message.parts).selectinload(MessagePart.thinking_part),
                    selectinload(Message.usage),
                )
                .all()
            )

        if not messages:
            redis_client.set(session_id, pickle.dumps([]))
            return []

        history = [_message_row_to_model(message) for message in messages]
        redis_client.set(session_id, pickle.dumps(history))
        return history

    @staticmethod
    def set(session_id: str, history: list[Any]) -> None:
        """Persist session history to Postgres and update Redis cache."""
        validated_history = list(ModelMessagesTypeAdapter.validate_python(history))

        with SessionLocal() as db:
            db_session = db.query(Session).filter(Session.session_id == session_id).first()
            if db_session is None:
                db_session = Session(session_id=session_id)
                db.add(db_session)
            db_session.updated_at = _utcnow()

            db.query(Message).filter(Message.session_id == session_id).delete(synchronize_session=False)
            db.flush()

            for idx, message in enumerate(validated_history):
                db_message = Message(
                    session_id=session_id,
                    sequence_index=idx,
                    kind=MessageKind.REQUEST if isinstance(message, ModelRequest) else MessageKind.RESPONSE,
                    instructions=message.instructions if isinstance(message, ModelRequest) else None,
                    model_name=message.model_name if isinstance(message, ModelResponse) else None,
                    timestamp=message.timestamp if isinstance(message, ModelResponse) else None,
                    vendor_details=message.vendor_details if isinstance(message, ModelResponse) else None,
                    vendor_id=message.vendor_id if isinstance(message, ModelResponse) else None,
                )
                db.add(db_message)
                db.flush()

                if isinstance(message, ModelResponse) and _usage_has_values(message.usage):
                    db_message.usage = MessageUsage(
                        requests=message.usage.requests,
                        request_tokens=message.usage.request_tokens,
                        response_tokens=message.usage.response_tokens,
                        total_tokens=message.usage.total_tokens,
                        details=message.usage.details,
                    )

                for part_index, part in enumerate(message.parts):
                    db_part = MessagePart(
                        message_id=db_message.id,
                        part_index=part_index,
                        part_type=_resolve_part_type(part),
                    )
                    _populate_part_payload(db_part, part)
                    db.add(db_part)

            db.commit()

        redis_client.set(session_id, pickle.dumps(validated_history))

    @staticmethod
    def delete(session_id: str) -> None:
        """Delete a session from both Postgres and Redis."""
        with SessionLocal() as db:
            db.query(Session).filter(Session.session_id == session_id).delete(synchronize_session=False)
            db.commit()
        redis_client.delete(session_id)


class Message(Base):
    __tablename__ = "session_messages"
    __table_args__ = (UniqueConstraint("session_id", "sequence_index", name="uq_session_message_order"),)

    id = Column(PGUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(String, ForeignKey("sessions.session_id", ondelete="CASCADE"), nullable=False)
    sequence_index = Column(Integer, nullable=False)
    kind = Column(SAEnum(MessageKind, name="message_kind"), nullable=False)
    instructions = Column(Text)
    model_name = Column(String)
    timestamp = Column(DateTime(timezone=True))
    vendor_details = Column(JSONB)
    vendor_id = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    parent_message_id = Column(PGUID(as_uuid=True), ForeignKey("session_messages.id", ondelete="SET NULL"))

    session = relationship("Session", back_populates="messages")
    usage = relationship("MessageUsage", back_populates="message", uselist=False, cascade="all, delete-orphan")
    parts = relationship(
        "MessagePart",
        back_populates="message",
        cascade="all, delete-orphan",
        order_by="MessagePart.part_index",
        passive_deletes=True,
    )


class MessageUsage(Base):
    __tablename__ = "session_message_usage"

    message_id = Column(PGUID(as_uuid=True), ForeignKey("session_messages.id", ondelete="CASCADE"), primary_key=True)
    requests = Column(Integer, default=0, nullable=False)
    request_tokens = Column(Integer)
    response_tokens = Column(Integer)
    total_tokens = Column(Integer)
    details = Column(JSONB)

    message = relationship("Message", back_populates="usage")


class MessagePart(Base):
    __tablename__ = "session_message_parts"
    __table_args__ = (UniqueConstraint("message_id", "part_index", name="uq_message_part_order"),)

    id = Column(PGUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(PGUID(as_uuid=True), ForeignKey("session_messages.id", ondelete="CASCADE"), nullable=False)
    part_index = Column(Integer, nullable=False)
    part_type = Column(SAEnum(PartType, name="message_part_type"), nullable=False)

    message = relationship("Message", back_populates="parts")
    system_prompt = relationship(
        "SystemPromptPartRow",
        back_populates="part",
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True,
    )
    user_prompt = relationship(
        "UserPromptPartRow",
        back_populates="part",
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True,
    )
    tool_return = relationship(
        "ToolReturnPartRow",
        back_populates="part",
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True,
    )
    retry_prompt = relationship(
        "RetryPromptPartRow",
        back_populates="part",
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True,
    )
    text_part = relationship(
        "TextPartRow",
        back_populates="part",
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True,
    )
    tool_call = relationship(
        "ToolCallPartRow",
        back_populates="part",
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True,
    )
    thinking_part = relationship(
        "ThinkingPartRow",
        back_populates="part",
        uselist=False,
        cascade="all, delete-orphan",
        single_parent=True,
    )


class SystemPromptPartRow(Base):
    __tablename__ = "system_prompt_parts"

    part_id = Column(PGUID(as_uuid=True), ForeignKey("session_message_parts.id", ondelete="CASCADE"), primary_key=True)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    dynamic_ref = Column(String)

    part = relationship("MessagePart", back_populates="system_prompt")


class UserPromptPartRow(Base):
    __tablename__ = "user_prompt_parts"

    part_id = Column(PGUID(as_uuid=True), ForeignKey("session_message_parts.id", ondelete="CASCADE"), primary_key=True)
    text_content = Column(Text)
    content_payload = Column(JSONB)
    timestamp = Column(DateTime(timezone=True), nullable=False)

    part = relationship("MessagePart", back_populates="user_prompt")


class ToolReturnPartRow(Base):
    __tablename__ = "tool_return_parts"

    part_id = Column(PGUID(as_uuid=True), ForeignKey("session_message_parts.id", ondelete="CASCADE"), primary_key=True)
    tool_name = Column(String, nullable=False)
    tool_call_id = Column(String, ForeignKey("tool_call_parts.tool_call_id", ondelete="SET NULL"))
    content = Column(JSONB, nullable=False)
    metadata = Column(JSONB)
    timestamp = Column(DateTime(timezone=True), nullable=False)

    part = relationship("MessagePart", back_populates="tool_return")


class RetryPromptPartRow(Base):
    __tablename__ = "retry_prompt_parts"

    part_id = Column(PGUID(as_uuid=True), ForeignKey("session_message_parts.id", ondelete="CASCADE"), primary_key=True)
    content_text = Column(Text)
    content_payload = Column(JSONB)
    tool_name = Column(String)
    tool_call_id = Column(String)
    timestamp = Column(DateTime(timezone=True), nullable=False)

    part = relationship("MessagePart", back_populates="retry_prompt")


class TextPartRow(Base):
    __tablename__ = "text_parts"

    part_id = Column(PGUID(as_uuid=True), ForeignKey("session_message_parts.id", ondelete="CASCADE"), primary_key=True)
    content = Column(Text, nullable=False)

    part = relationship("MessagePart", back_populates="text_part")


class ToolCallPartRow(Base):
    __tablename__ = "tool_call_parts"

    part_id = Column(PGUID(as_uuid=True), ForeignKey("session_message_parts.id", ondelete="CASCADE"), primary_key=True)
    tool_name = Column(String, nullable=False)
    tool_call_id = Column(String, unique=True, nullable=False)
    args_json = Column(JSONB)
    args_text = Column(Text)

    part = relationship("MessagePart", back_populates="tool_call")


class ThinkingPartRow(Base):
    __tablename__ = "thinking_parts"

    part_id = Column(PGUID(as_uuid=True), ForeignKey("session_message_parts.id", ondelete="CASCADE"), primary_key=True)
    content = Column(Text, nullable=False)
    signature = Column(String)
    identifier = Column(String)

    part = relationship("MessagePart", back_populates="thinking_part")


def _usage_has_values(usage: Usage) -> bool:
    return bool(usage.requests or usage.request_tokens or usage.response_tokens or usage.total_tokens or usage.details)


def _message_row_to_model(message: Message) -> ModelMessage:
    parts = [_part_row_to_model(part) for part in message.parts]
    if message.kind == MessageKind.REQUEST:
        return ModelRequest(parts=parts, instructions=message.instructions)

    usage = message.usage or MessageUsage(requests=0)
    return ModelResponse(
        parts=parts,
        usage=Usage(
            requests=usage.requests,
            request_tokens=usage.request_tokens,
            response_tokens=usage.response_tokens,
            total_tokens=usage.total_tokens,
            details=usage.details,
        ),
        model_name=message.model_name,
        timestamp=message.timestamp or message.created_at,
        vendor_details=message.vendor_details,
        vendor_id=message.vendor_id,
    )


def _part_row_to_model(part: MessagePart) -> Any:
    if part.part_type == PartType.SYSTEM_PROMPT and part.system_prompt:
        data = part.system_prompt
        return SystemPromptPart(content=data.content, timestamp=data.timestamp, dynamic_ref=data.dynamic_ref)
    if part.part_type == PartType.USER_PROMPT and part.user_prompt:
        data = part.user_prompt
        if data.text_content is not None:
            content: Any = data.text_content
        else:
            content = [_deserialize_user_content(item) for item in data.content_payload or []]
        return UserPromptPart(content=content, timestamp=data.timestamp)
    if part.part_type == PartType.TOOL_RETURN and part.tool_return:
        data = part.tool_return
        return ToolReturnPart(
            tool_name=data.tool_name,
            content=tool_return_ta.validate_python(data.content),
            tool_call_id=data.tool_call_id or "",
            metadata=tool_return_ta.validate_python(data.metadata) if data.metadata is not None else None,
            timestamp=data.timestamp,
        )
    if part.part_type == PartType.RETRY_PROMPT and part.retry_prompt:
        data = part.retry_prompt
        if data.content_text is not None:
            content = data.content_text
        else:
            content = error_details_ta.validate_python(data.content_payload or [])
        return RetryPromptPart(
            content=content,
            tool_name=data.tool_name,
            tool_call_id=data.tool_call_id or "",
            timestamp=data.timestamp,
        )
    if part.part_type == PartType.TEXT and part.text_part:
        return TextPart(content=part.text_part.content)
    if part.part_type == PartType.TOOL_CALL and part.tool_call:
        data = part.tool_call
        args: Any
        if data.args_json is not None:
            args = data.args_json
        else:
            args = data.args_text
        return ToolCallPart(tool_name=data.tool_name, args=args, tool_call_id=data.tool_call_id)
    if part.part_type == PartType.THINKING and part.thinking_part:
        data = part.thinking_part
        return ThinkingPart(content=data.content, signature=data.signature, id=data.identifier)
    raise ValueError(f"Unsupported part type {part.part_type}")


def _resolve_part_type(part: Any) -> PartType:
    if isinstance(part, SystemPromptPart):
        return PartType.SYSTEM_PROMPT
    if isinstance(part, UserPromptPart):
        return PartType.USER_PROMPT
    if isinstance(part, ToolReturnPart):
        return PartType.TOOL_RETURN
    if isinstance(part, RetryPromptPart):
        return PartType.RETRY_PROMPT
    if isinstance(part, TextPart):
        return PartType.TEXT
    if isinstance(part, ToolCallPart):
        return PartType.TOOL_CALL
    if isinstance(part, ThinkingPart):
        return PartType.THINKING
    raise ValueError(f"Unsupported part instance {type(part)!r}")


def _populate_part_payload(db_part: MessagePart, part: Any) -> None:
    if isinstance(part, SystemPromptPart):
        db_part.system_prompt = SystemPromptPartRow(
            content=part.content,
            timestamp=part.timestamp,
            dynamic_ref=part.dynamic_ref,
        )
    elif isinstance(part, UserPromptPart):
        text_content, payload = _serialize_user_prompt_content(part.content)
        db_part.user_prompt = UserPromptPartRow(
            text_content=text_content,
            content_payload=payload,
            timestamp=part.timestamp,
        )
    elif isinstance(part, ToolReturnPart):
        db_part.tool_return = ToolReturnPartRow(
            tool_name=part.tool_name,
            tool_call_id=part.tool_call_id,
            content=tool_return_ta.dump_python(part.content, mode="json"),
            metadata=tool_return_ta.dump_python(part.metadata, mode="json") if part.metadata is not None else None,
            timestamp=part.timestamp,
        )
    elif isinstance(part, RetryPromptPart):
        content_text: str | None = None
        content_payload: Any | None = None
        if isinstance(part.content, str):
            content_text = part.content
        else:
            content_payload = error_details_ta.dump_python(part.content, mode="json")
        db_part.retry_prompt = RetryPromptPartRow(
            content_text=content_text,
            content_payload=content_payload,
            tool_name=part.tool_name,
            tool_call_id=part.tool_call_id,
            timestamp=part.timestamp,
        )
    elif isinstance(part, TextPart):
        db_part.text_part = TextPartRow(content=part.content)
    elif isinstance(part, ToolCallPart):
        args_json: Any | None = None
        args_text: str | None = None
        if isinstance(part.args, dict):
            args_json = part.args
        elif isinstance(part.args, str):
            args_text = part.args
        db_part.tool_call = ToolCallPartRow(
            tool_name=part.tool_name,
            tool_call_id=part.tool_call_id,
            args_json=args_json,
            args_text=args_text,
        )
    elif isinstance(part, ThinkingPart):
        db_part.thinking_part = ThinkingPartRow(
            content=part.content,
            signature=part.signature,
            identifier=part.id,
        )
    else:
        raise ValueError(f"Unsupported part instance {type(part)!r}")


def _serialize_user_prompt_content(content: Any) -> tuple[str | None, list[dict[str, Any]] | None]:
    if isinstance(content, str):
        return content, None
    payload = [_serialize_user_content(item) for item in content]
    return None, payload


def _serialize_user_content(item: Any) -> dict[str, Any]:
    if isinstance(item, str):
        return {"type": "text", "text": item}
    if isinstance(item, BinaryContent):
        encoded = base64.b64encode(item.data).decode("utf-8")
        return {
            "type": "binary",
            "media_type": item.media_type,
            "identifier": item.identifier,
            "vendor_metadata": item.vendor_metadata,
            "data": encoded,
        }
    if isinstance(item, (ImageUrl, AudioUrl, DocumentUrl, VideoUrl)):
        return {
            "type": item.kind,
            "url": item.url,
            "force_download": item.force_download,
            "vendor_metadata": item.vendor_metadata,
            "media_type": item.media_type,
        }
    raise ValueError(f"Unsupported user content type {type(item)!r}")


def _deserialize_user_content(payload: dict[str, Any]) -> Any:
    content_type = payload.get("type")
    if content_type == "text":
        return payload.get("text", "")
    if content_type == "binary":
        data = base64.b64decode(payload.get("data", "")) if payload.get("data") else b""
        return BinaryContent(
            data=data,
            media_type=payload.get("media_type", "application/octet-stream"),
            identifier=payload.get("identifier"),
            vendor_metadata=payload.get("vendor_metadata"),
        )

    cls_map = {
        "image-url": ImageUrl,
        "audio-url": AudioUrl,
        "document-url": DocumentUrl,
        "video-url": VideoUrl,
    }
    cls = cls_map.get(content_type)
    if cls is None:
        raise ValueError(f"Unknown user content type {content_type}")
    return cls(
        url=payload.get("url", ""),
        force_download=payload.get("force_download", False),
        vendor_metadata=payload.get("vendor_metadata"),
        media_type=payload.get("media_type"),
        kind=content_type,
    )
