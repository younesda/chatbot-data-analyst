#schemas.py
from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import List, Optional, Any, Dict

# User schemas
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse

# CSV schemas
class CSVUploadResponse(BaseModel):
    file_id: int
    filename: str
    info: Dict[str, Any]
    message: str

class CSVFileResponse(BaseModel):
    id: int
    filename: str
    file_size: int
    columns: List[str]
    row_count: int
    created_at: datetime

# Chat schemas
class ChatSessionCreate(BaseModel):
    csv_file_id: int
    title: Optional[str] = None

class ChatSessionResponse(BaseModel):
    id: int
    title: str
    csv_file_id: int
    created_at: datetime

class MessageCreate(BaseModel):
    content: str
    request_type: str  # "dashboard", "chart", "table", "explanation"

class MessageResponse(BaseModel):
    id: int
    content: str
    is_user: bool
    created_at: datetime
    visualization_data: Optional[Dict[str, Any]] = None
    chart_config: Optional[Dict[str, Any]] = None
