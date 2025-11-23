from typing import Annotated
from fastapi import Depends
from app.database.database import SessionLocal
from sqlalchemy.orm import Session

def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    finally:
        db.close()
        
db_debends = Annotated[Session, Depends(get_db)]
