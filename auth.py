#auth.py
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import SessionLocal
from models import User

load_dotenv()

# Configuration Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL environment variable is required")

if not SUPABASE_JWT_SECRET:
    raise ValueError("SUPABASE_JWT_SECRET environment variable is required")

# Client Supabase
supabase: Client = create_client(
    SUPABASE_URL, 
    SUPABASE_SERVICE_KEY or "dummy_key"
)

security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Authentification via Supabase Auth"""
    token = credentials.credentials
    
    try:
        # Vérifier le token avec Supabase
        response = supabase.auth.get_user(token)
        
        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide"
            )
        
        supabase_user = response.user
        
        # Chercher l'utilisateur dans notre base locale
        user = db.query(User).filter(
            (User.email == supabase_user.email) | 
            (User.supabase_id == supabase_user.id)
        ).first()
        
        # Créer l'utilisateur s'il n'existe pas
        if not user:
            username = supabase_user.email.split('@')[0]
            user = User(
                email=supabase_user.email,
                username=username,
                supabase_id=supabase_user.id
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Nouvel utilisateur créé: {user.email}")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Erreur authentification: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Échec de l'authentification"
        )
