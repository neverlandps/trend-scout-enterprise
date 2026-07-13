from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from trend_scout_enterprise.core.database import get_db

router = APIRouter()


@router.get("/sources")
def list_sources(db: Session = Depends(get_db)):
    return {"sources": []}


@router.post("/sources")
def create_source(source: dict, db: Session = Depends(get_db)):
    return {"id": "placeholder", "source": source}


@router.get("/sources/{source_id}")
def get_source(source_id: str, db: Session = Depends(get_db)):
    return {"id": source_id, "name": "placeholder"}


@router.put("/sources/{source_id}")
def update_source(source_id: str, source: dict, db: Session = Depends(get_db)):
    return {"id": source_id, "source": source}


@router.delete("/sources/{source_id}")
def delete_source(source_id: str, db: Session = Depends(get_db)):
    return {"deleted": source_id}
