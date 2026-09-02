from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime, timezone
from app.models.base import Base

class DocumentChat(Base):
    __tablename__ = "document_chats"

    document_id = Column(String, ForeignKey("documents.id"), primary_key=True)
    chat_id = Column(String, ForeignKey("chats.id"), primary_key=True)

    document = relationship("Document", back_populates="chats")
    chat = relationship("Chat", back_populates="documents")

class Chat(Base):
    __tablename__ = "chats"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    title = Column(String, default="New Chat")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="chats")
    documents = relationship("DocumentChat", back_populates="chat", cascade="all, delete-orphan")
    messages = relationship("Message", back_populates="chat", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String, ForeignKey("chats.id"), nullable=False)
    role = Column(String, nullable=False) # 'user' or 'ai'
    content = Column(String, nullable=False)
    sources = Column(String, nullable=True) # JSON string of sources
    feedback = Column(Boolean, nullable=True) # True (helpful), False (unhelpful), None (no feedback)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    chat = relationship("Chat", back_populates="messages")
