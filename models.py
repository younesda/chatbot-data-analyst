#models.py
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, LargeBinary
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    supabase_id = Column(String(255), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relations
    csv_files = relationship("CSVFile", back_populates="user", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", back_populates="user", cascade="all, delete-orphan")

class CSVFile(Base):
    __tablename__ = "csv_files"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    columns = Column(JSON, nullable=False)
    row_count = Column(Integer, nullable=False)
    file_data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relations
    user = relationship("User", back_populates="csv_files")
    chat_sessions = relationship("ChatSession", back_populates="csv_file", cascade="all, delete-orphan")

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    csv_file_id = Column(Integer, ForeignKey("csv_files.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relations
    user = relationship("User", back_populates="chat_sessions")
    csv_file = relationship("CSVFile", back_populates="chat_sessions")
    messages = relationship("Message", back_populates="chat_session", cascade="all, delete-orphan")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    is_user = Column(Boolean, nullable=False)
    visualization_data = Column(JSON, nullable=True)
    chart_config = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relations
    chat_session = relationship("ChatSession", back_populates="messages")
