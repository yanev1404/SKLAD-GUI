from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone
from .. import models
from ..database import get_db
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/events", tags=["Events"])

class EventCreate(BaseModel):
    short_name:  str
    event_type:  Optional[str] = None
    location_id: Optional[int] = None
    contact_id:  Optional[int] = None
    start_date:  Optional[datetime] = None
    end_date:    Optional[datetime] = None
    description: Optional[str] = None

class EventOut(BaseModel):
    event_id:    int
    short_name:  str
    event_type:  Optional[str]
    location_id: Optional[int]
    contact_id:  Optional[int]
    start_date:  Optional[datetime]
    end_date:    Optional[datetime]
    description: Optional[str]
    class Config: from_attributes = True

@router.get("/", response_model=list[EventOut])
def list_events(db: Session = Depends(get_db)):
    return db.query(models.Event).order_by(models.Event.start_date.desc()).all()

@router.get("/active", response_model=list[EventOut])
def active_events(db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    return db.query(models.Event).filter(
        models.Event.start_date <= now,
        models.Event.end_date   >= now
    ).all()

@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Event, event_id)
    if not obj: raise HTTPException(404, "Event not found")
    return obj

@router.post("/", response_model=EventOut, status_code=201)
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    obj = models.Event(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj

@router.put("/{event_id}", response_model=EventOut)
def update_event(event_id: int, payload: EventCreate, db: Session = Depends(get_db)):
    obj = db.get(models.Event, event_id)
    if not obj: raise HTTPException(404, "Event not found")
    for k, v in payload.model_dump().items(): setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj

@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Event, event_id)
    if not obj: raise HTTPException(404, "Event not found")
    db.delete(obj); db.commit()
