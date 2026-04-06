from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/statuses", tags=["Statuses"])


@router.get("/", response_model=list[schemas.StatusOut])
def list_statuses(db: Session = Depends(get_db)):
    return db.query(models.Status).order_by(models.Status.name).all()


@router.post("/", response_model=schemas.StatusOut, status_code=201)
def create_status(payload: schemas.StatusCreate, db: Session = Depends(get_db)):
    existing = db.query(models.Status).filter(models.Status.name == payload.name).first()
    if existing:
        raise HTTPException(400, "Status name already exists")
    obj = models.Status(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{status_id}", status_code=204)
def delete_status(status_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Status, status_id)
    if not obj:
        raise HTTPException(404, "Status not found")
    # Prevent deleting statuses in use
    in_use = db.query(models.Fixture).filter(models.Fixture.status_id == status_id).count()
    if in_use:
        raise HTTPException(409, f"Status is assigned to {in_use} fixture(s) — reassign them first")
    db.delete(obj)
    db.commit()
