from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/contacts", tags=["Contacts"])


@router.get("/", response_model=list[schemas.ContactOut])
def list_contacts(db: Session = Depends(get_db)):
    return db.query(models.Contact).order_by(models.Contact.company, models.Contact.last_name).all()


@router.get("/{contact_id}", response_model=schemas.ContactOut)
def get_contact(contact_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Contact, contact_id)
    if not obj:
        raise HTTPException(404, "Contact not found")
    return obj


@router.post("/", response_model=schemas.ContactOut, status_code=201)
def create_contact(payload: schemas.ContactCreate, db: Session = Depends(get_db)):
    obj = models.Contact(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{contact_id}", response_model=schemas.ContactOut)
def update_contact(contact_id: int, payload: schemas.ContactCreate, db: Session = Depends(get_db)):
    obj = db.get(models.Contact, contact_id)
    if not obj:
        raise HTTPException(404, "Contact not found")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{contact_id}", status_code=204)
def delete_contact(contact_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Contact, contact_id)
    if not obj:
        raise HTTPException(404, "Contact not found")
    db.delete(obj)
    db.commit()
