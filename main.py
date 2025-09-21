import os
import io
from datetime import datetime
from typing import List
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import pandas as pd

from database import SessionLocal, engine, Base
from models import User, CSVFile, ChatSession, Message
from auth import get_current_user, verify_password, get_password_hash, create_access_token, get_db
from claude_service import ClaudeService
from schemas import *

# Create all tables
print("🗄️ Creating database tables...")
Base.metadata.create_all(bind=engine)
print("✅ Database tables created successfully")

app = FastAPI(
    title="YounesAI API",
    description="API pour l'analyse de données CSV avec IA",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Claude service
claude_service = ClaudeService()

# Health check endpoints
@app.get("/")
async def root():
    return {
        "message": "🚀 YounesAI API is running!",
        "version": "1.0.0",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "features": [
            "CSV Upload & Processing",
            "AI-Powered Data Analysis",
            "Interactive Chat Interface", 
            "Dashboard Generation",
            "Data Visualization"
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "healthy"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return {
        "status": "healthy",
        "database": db_status,
        "claude_service": "initialized",
        "timestamp": datetime.utcnow().isoformat()
    }

# Authentication endpoints
@app.post("/auth/register", response_model=UserResponse)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(
            (User.email == user_data.email) | (User.username == user_data.username)
        ).first()
        
        if existing_user:
            if existing_user.email == user_data.email:
                raise HTTPException(status_code=400, detail="Email already registered")
            else:
                raise HTTPException(status_code=400, detail="Username already taken")
        
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
        
        print(f"✅ New user registered: {user_data.email}")
        
        return UserResponse(
            id=db_user.id,
            email=db_user.email,
            username=db_user.username,
            created_at=db_user.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        print(f"❌ Registration error: {e}")
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")

@app.post("/auth/login", response_model=TokenResponse)
async def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """Login user and return JWT token"""
    try:
        # Find user
        user = db.query(User).filter(User.email == credentials.email).first()
        
        if not user or not verify_password(credentials.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Create access token
        access_token = create_access_token(data={"user_id": user.id})
        
        print(f"✅ User logged in: {credentials.email}")
        
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
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Login error: {e}")
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")

# CSV file endpoints
@app.post("/csv/upload", response_model=CSVUploadResponse)
async def upload_csv(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and process CSV file"""
    # Validate file type
    if not file.filename or not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    try:
        # Read file content
        contents = await file.read()
        if len(contents) == 0:
            raise HTTPException(status_code=400, detail="File is empty")
        
        # Parse CSV
        try:
            df = pd.read_csv(io.StringIO(contents.decode('utf-8')))
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")
        
        if df.empty:
            raise HTTPException(status_code=400, detail="CSV file contains no data")
        
        # Store file in database
        csv_file = CSVFile(
            user_id=current_user.id,
            filename=file.filename,
            file_size=len(contents),
            columns=list(df.columns),
            row_count=len(df),
            file_data=contents
        )
        
        db.add(csv_file)
        db.commit()
        db.refresh(csv_file)
        
        print(f"📁 CSV uploaded: {file.filename} ({len(df)} rows, {len(df.columns)} columns)")
        
        # Prepare file info
        info = {
            "shape": list(df.shape),
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
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Upload error: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/csv/files", response_model=List[CSVFileResponse])
async def get_csv_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all CSV files for current user"""
    files = db.query(CSVFile).filter(CSVFile.user_id == current_user.id).order_by(CSVFile.created_at.desc()).all()
    
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

# Chat session endpoints
@app.post("/chat/sessions", response_model=ChatSessionResponse)
async def create_chat_session(
    session_data: ChatSessionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new chat session"""
    # Verify CSV file belongs to user
    csv_file = db.query(CSVFile).filter(
        CSVFile.id == session_data.csv_file_id,
        CSVFile.user_id == current_user.id
    ).first()
    
    if not csv_file:
        raise HTTPException(status_code=404, detail="CSV file not found")
    
    # Create session
    title = session_data.title or f"Analyse de {csv_file.filename}"
    chat_session = ChatSession(
        user_id=current_user.id,
        csv_file_id=session_data.csv_file_id,
        title=title
    )
    
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    
    print(f"💬 New chat session created: {title}")
    
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
    """Get all chat sessions for current user"""
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

@app.post("/chat/sessions/{session_id}/messages", response_model=MessageResponse)
async def send_message(
    session_id: int,
    message_data: MessageCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Send a message and get AI response"""
    # Verify session belongs to user
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    # Get CSV data
    csv_file = db.query(CSVFile).filter(CSVFile.id == session.csv_file_id).first()
    if not csv_file:
        raise HTTPException(status_code=404, detail="CSV file not found")
    
    try:
        df = pd.read_csv(io.StringIO(csv_file.file_data.decode('utf-8')))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading CSV: {str(e)}")
    
    # Save user message
    user_message = Message(
        chat_session_id=session_id,
        content=message_data.content,
        is_user=True
    )
    db.add(user_message)
    db.commit()
    
    try:
        print(f"🤖 Processing {message_data.request_type} request: {message_data.content[:50]}...")
        
        # Get Claude response
        response = await claude_service.analyze_data(
            user_query=message_data.content,
            df=df,
            request_type=message_data.request_type,
            session_id=session_id
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
        
        print(f"✅ AI response generated successfully")
        
        return MessageResponse(
            id=claude_message.id,
            content=claude_message.content,
            is_user=claude_message.is_user,
            created_at=claude_message.created_at,
            visualization_data=claude_message.visualization_data,
            chart_config=claude_message.chart_config
        )
        
    except Exception as e:
        db.rollback()
        print(f"❌ Message processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing message: {str(e)}")

@app.get("/chat/sessions/{session_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all messages for a chat session"""
    # Verify session belongs to user
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
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

# Dashboard endpoints
@app.get("/dashboard/{session_id}", response_model=DashboardResponse)
async def get_dashboard(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get full dashboard for a session"""
    # Verify session belongs to user
    session = db.query(ChatSession).filter(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    
    # Get CSV data
    csv_file = db.query(CSVFile).filter(CSVFile.id == session.csv_file_id).first()
    if not csv_file:
        raise HTTPException(status_code=404, detail="CSV file not found")
    
    try:
        df = pd.read_csv(io.StringIO(csv_file.file_data.decode('utf-8')))
        
        print(f"📊 Generating dashboard for session {session_id}...")
        
        # Generate comprehensive dashboard
        dashboard_data = await claude_service.create_full_dashboard(df)
        
        print(f"✅ Dashboard generated successfully")
        
        return DashboardResponse(
            session_id=session_id,
            title=session.title,
            kpis=dashboard_data["kpis"],
            charts=dashboard_data["charts"],
            summary=dashboard_data["summary"],
            metadata=dashboard_data["metadata"]
        )
        
    except Exception as e:
        print(f"❌ Dashboard error: {e}")
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting YounesAI API server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)
