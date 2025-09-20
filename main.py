#main.py
from dotenv import load_dotenv
import os
load_dotenv()

# Maintenant les autres imports
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import pandas as pd
import json
import io
import base64
from datetime import datetime, timedelta
from typing import List, Optional

from database import SessionLocal, engine
from models import Base, User, ChatSession, Message, CSVFile
from auth import get_current_user, create_access_token, verify_password, get_password_hash
from claude_service import ClaudeService
from schemas import *

# Create tables
# Base.metadata.create_all(bind=engine)  # Commenté temporairement

app = FastAPI(title="CSV Chatbot API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoint de test pour voir si l'app fonctionne
@app.get("/")
async def root():
    return {"message": "API is running!"}

@app.get("/test-db")
async def test_db():
    try:
        from sqlalchemy import text  # Ajoutez cet import
        db = SessionLocal()
        db.execute(text("SELECT 1"))  # ✅ Version corrigée
        db.close()
        return {"message": "Database connection OK!"}
    except Exception as e:
        return {"error": str(e)}

security = HTTPBearer()
claude_service = ClaudeService()

# Database dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Auth routes
@app.post("/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    hashed_password = get_password_hash(user_data.password)
    db_user = User(
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return UserResponse(
        id=db_user.id,
        email=db_user.email,
        username=db_user.username,
        created_at=db_user.created_at
    )

@app.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == credentials.email).first()
    
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    access_token = create_access_token(data={"user_id": user.id})
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            created_at=user.created_at
        )
    )

# CSV upload
@app.post("/csv/upload", response_model=CSVUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only CSV files are allowed"
        )
    
    try:
        # Read and validate CSV
        contents = await file.read()
        df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        
        # Store file info in database
        csv_file = CSVFile(
            user_id=current_user.id,
            filename=file.filename,
            file_size=len(contents),
            columns=list(df.columns),
            row_count=len(df),
            file_data=contents  # In production, store in cloud storage
        )
        
        db.add(csv_file)
        db.commit()
        db.refresh(csv_file)
        
        # Get basic info about the CSV
        info = {
            "shape": df.shape,
            "columns": list(df.columns),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "sample": df.head(3).to_dict('records'),
            "null_counts": df.isnull().sum().to_dict()
        }
        
        return CSVUploadResponse(
            file_id=csv_file.id,
            filename=file.filename,
            info=info,
            message="CSV uploaded successfully"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error processing CSV: {str(e)}"
        )

# Chat sessions
@app.post("/chat/sessions", response_model=ChatSessionResponse)
async def create_chat_session(
    session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify CSV file belongs to user
    csv_file = db.query(CSVFile).filter(
        CSVFile.id == session_data.csv_file_id,
        CSVFile.user_id == current_user.id
    ).first()
    
    if not csv_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="CSV file not found"
        )
    
    chat_session = ChatSession(
        user_id=current_user.id,
        csv_file_id=session_data.csv_file_id,
        title=session_data.title or f"Analysis of {csv_file.filename}"
    )
    
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    
    return ChatSessionResponse(
        id=chat_session.id,
        title=chat_session.title,
        csv_file_id=chat_session.csv_file_id,
        created_at=chat_session.created_at
    )

@app.get("/chat/sessions", response_model=List[ChatSessionResponse])
async def get_chat_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    sessions = db.query(ChatSession).filter(
        ChatSession.user_id == current_user.id
    ).order_by(ChatSession.updated_at.desc()).all()
    
    return [
        ChatSessionResponse(
            id=session.id,
            title=session.title,
            csv_file_id=session.csv_file_id,
            created_at=session.created_at
        )
        for session in sessions
    ]

# Chat messages
@app.post("/chat/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(
    session_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify session belongs to user
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    # Get CSV data
    csv_file = db.query(CSVFile).filter(CSVFile.id == session.csv_file_id).first()
    df = pd.read_csv(io.StringIO(csv_file.file_data.decode('utf-8')))
    
    # Save user message
    user_message = Message(
        chat_session_id=session_id,
        content=message_data.content,
        is_user=True
    )
    db.add(user_message)
    db.commit()
    
    try:
        # Get Claude response
        response = await claude_service.analyze_data(
            user_query=message_data.content,
            df=df,
            request_type=message_data.request_type
        )
        
        # Save Claude response
        claude_message = Message(
            chat_session_id=session_id,
            content=response["text"],
            is_user=False,
            visualization_data=response.get("visualization"),
            chart_config=response.get("chart_config")
        )
        db.add(claude_message)
        
        # Update session timestamp
        session.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(claude_message)
        
        return MessageResponse(
            id=claude_message.id,
            content=claude_message.content,
            is_user=claude_message.is_user,
            created_at=claude_message.created_at,
            visualization_data=claude_message.visualization_data,
            chart_config=claude_message.chart_config
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}"
        )

@app.get("/chat/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_chat_history(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Verify session belongs to user
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    messages = db.query(Message).filter(
        Message.chat_session_id == session_id
    ).order_by(Message.created_at.asc()).all()
    
    return [
        MessageResponse(
            id=message.id,
            content=message.content,
            is_user=message.is_user,
            created_at=message.created_at,
            visualization_data=message.visualization_data,
            chart_config=message.chart_config
        )
        for message in messages
    ]

# Dashboard endpoint
@app.get("/dashboard/{session_id}", response_model=DashboardResponse)
async def get_dashboard(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Get CSV data
    csv_file = db.query(CSVFile).filter(CSVFile.id == session.csv_file_id).first()
    df = pd.read_csv(io.StringIO(csv_file.file_data.decode('utf-8')))
    
    # Generate comprehensive dashboard
    dashboard = await claude_service.create_full_dashboard(df)
    
    return DashboardResponse(
        session_id=session_id,
        title=session.title,
        kpis=dashboard["kpis"],
        charts=dashboard["charts"],
        filters=dashboard["filters"],
        data_summary=dashboard["summary"]
    )

# Filter dashboard data
@app.post("/dashboard/{session_id}/filter")
async def filter_dashboard(
    session_id: int,
    filter_data: DashboardFilterRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Apply filters and return updated data
    pass

# User's CSV files
@app.get("/csv/files", response_model=List[CSVFileResponse])
async def get_user_csv_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    files = db.query(CSVFile).filter(
        CSVFile.user_id == current_user.id
    ).order_by(CSVFile.created_at.desc()).all()
    
    return [
        CSVFileResponse(
            id=file.id,
            filename=file.filename,
            file_size=file.file_size,
            columns=file.columns,
            row_count=file.row_count,
            created_at=file.created_at
        )
        for file in files
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
