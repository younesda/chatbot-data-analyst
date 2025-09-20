#auth.py
from dotenv import load_dotenv
load_dotenv()

from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import create_client, Client
import os
import jwt
from typing import Optional
from sqlalchemy.orm import Session
from models import User
from database import SessionLocal

# Configuration Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://mcorowrazvgxvnkhvgtz.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

if not SUPABASE_SERVICE_KEY:
    raise ValueError("SUPABASE_SERVICE_KEY must be set in environment variables")

# Client Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

security = HTTPBearer()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def verify_supabase_token(token: str) -> Optional[dict]:
    """Vérifie un token Supabase et retourne les données utilisateur"""
    try:
        # Méthode 1: Vérification via l'API Supabase
        headers = {
            'Authorization': f'Bearer {token}',
            'apikey': SUPABASE_SERVICE_KEY
        }
        
        # Test du token en appelant l'API utilisateur
        response = supabase.auth.get_user(token)
        
        if response.user:
            return {
                'id': response.user.id,
                'email': response.user.email,
                'user_metadata': response.user.user_metadata
            }
        
        return None
        
    except Exception as e:
        print(f"Erreur vérification token Supabase: {e}")
        return None

async def get_current_user_supabase(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Récupère l'utilisateur actuel depuis le token Supabase"""
    
    token = credentials.credentials
    
    # Vérifie le token Supabase
    supabase_user = await verify_supabase_token(token)
    
    if not supabase_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Supabase authentication credentials"
        )
    
    # Trouve ou crée l'utilisateur dans ta base locale
    user = db.query(User).filter(User.email == supabase_user['email']).first()
    
    if not user:
        # Crée l'utilisateur s'il n'existe pas
        user = User(
            email=supabase_user['email'],
            username=supabase_user.get('user_metadata', {}).get('username', supabase_user['email'].split('@')[0]),
            hashed_password="supabase_auth"  # Pas utilisé avec Supabase
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    
    return user

# GARDE AUSSI L'ANCIEN SYSTÈME POUR COMPATIBILITÉ
from datetime import datetime, timedelta
from jose import JWTError, jwt as jose_jwt
from passlib.context import CryptContext

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable must be set")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 heures

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jose_jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    try:
        payload = jose_jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None

async def get_current_user_jwt(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Ancien système JWT pour compatibilité"""
    token = credentials.credentials
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid JWT authentication credentials"
        )
    
    user = db.query(User).filter(User.id == payload.get("user_id")).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user

# FONCTION HYBRIDE QUI ESSAIE LES DEUX
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Essaie d'abord Supabase, puis JWT si ça échoue"""
    
    token = credentials.credentials
    
    # Essaie d'abord l'auth Supabase
    try:
        supabase_user = await verify_supabase_token(token)
        
        if supabase_user:
            # Trouve ou crée l'utilisateur
            user = db.query(User).filter(User.email == supabase_user['email']).first()
            
            if not user:
                user = User(
                    email=supabase_user['email'],
                    username=supabase_user.get('user_metadata', {}).get('username', supabase_user['email'].split('@')[0]),
                    hashed_password="supabase_auth"
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            
            return user
    except Exception as e:
        print(f"Auth Supabase échouée, essai JWT: {e}")
    
    # Si Supabase échoue, essaie JWT
    try:
        payload = verify_token(token)
        if payload:
            user = db.query(User).filter(User.id == payload.get("user_id")).first()
            if user:
                return user
    except Exception as e:
        print(f"Auth JWT échouée: {e}")
    
    # Si les deux échouent
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials"
    )
