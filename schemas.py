#schemas.py
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import List, Optional, Any, Dict

class UserCreate(BaseModel):
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)

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
    token_type: str = "bearer"
    user: UserResponse

class CSVUploadResponse(BaseModel):
    file_id: int
    filename: str
    info: Dict[str, Any]
    message: str = "CSV uploaded successfully"

class CSVFileResponse(BaseModel):
    id: int
    filename: str
    file_size: int
    columns: List[str]
    row_count: int
    created_at: datetime

class ChatSessionCreate(BaseModel):
    csv_file_id: int
    title: Optional[str] = None

class ChatSessionResponse(BaseModel):
    id: int
    title: str
    csv_file_id: int
    created_at: datetime

class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1)
    request_type: str = Field(..., pattern="^(explanation|chart|table|dashboard)$")
    
class MessageResponse(BaseModel):
    id: int
    content: str
    is_user: bool
    created_at: datetime
    visualization_data: Optional[Dict[str, Any]] = None
    chart_config: Optional[Dict[str, Any]] = None

class DashboardResponse(BaseModel):
    session_id: int
    title: str
    kpis: List[Dict[str, Any]]
    charts: List[Dict[str, Any]]
    summary: Dict[str, Any]
    metadata: Dict[str, Any]
