from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, LargeBinary
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relations
    csv_files = relationship("CSVFile", back_populates="user")
    chat_sessions = relationship("ChatSession", back_populates="user")

class CSVFile(Base):
    __tablename__ = "csv_files"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    filename = Column(String, nullable=False)
    file_size = Column(Integer, nullable=False)
    columns = Column(JSON, nullable=False)  # List of column names
    row_count = Column(Integer, nullable=False)
    file_data = Column(LargeBinary, nullable=False)  # Store CSV content
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relations
    user = relationship("User", back_populates="csv_files")
    chat_sessions = relationship("ChatSession", back_populates="csv_file")

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    csv_file_id = Column(Integer, ForeignKey("csv_files.id"), nullable=False)
    title = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relations
    user = relationship("User", back_populates="chat_sessions")
    csv_file = relationship("CSVFile", back_populates="chat_sessions")
    messages = relationship("Message", back_populates="chat_session")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_user = Column(Boolean, nullable=False)
    visualization_data = Column(JSON, nullable=True)  # Chart/dashboard data
    chart_config = Column(JSON, nullable=True)  # Chart configuration
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relations
    chat_session = relationship("ChatSession", back_populates="messages")