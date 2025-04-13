from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import get_settings

settings = get_settings()

# Pridáme parametre pre UTF-8 kódovanie
DATABASE_URL = settings.DATABASE_URL
if "postgresql" in DATABASE_URL:
    if "?" not in DATABASE_URL:
        DATABASE_URL += "?"
    else:
        DATABASE_URL += "&"
    DATABASE_URL += "client_encoding=utf8&options=-c%20client_encoding=utf8"

engine = create_engine(
    DATABASE_URL,
    connect_args={
        "options": "-c client_encoding=utf8"
    }
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 