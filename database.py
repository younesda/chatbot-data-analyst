from dotenv import load_dotenv
load_dotenv()  # IMPORTANT: Charger avant os.getenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL must be set in .env file")

# Configuration pour SQLite ou PostgreSQL
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # Pour SQLite
        echo=False
    )
else:
    engine = create_engine(
        DATABASE_URL,
        connect_args={"client_encoding": "utf8"},  # Pour PostgreSQL
        echo=False
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)