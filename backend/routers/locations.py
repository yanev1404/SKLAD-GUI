from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/locations", tags=["Locations"])


def _create_placeholder(location: models.Location, db: Session) -> models.Container:
    """Create (or return existing) placeholder container for a location."""
    existing = db.query(models.Container).filter(
        models.Container.location_id == location.location_id,
        models.Container.container_type == "placeholder"
    ).first()
    if existing:
        return existing

    placeholder = models.Container(
        category="placeholder",
        container_type="placeholder",
        short_name=location.short_name,
        location_id=location.location_id,
        note=f"Auto-generated placeholder for {location.short_name}"
    )
    db.add(placeholder)
    db.flush()  # get container_id before commit
    location.placeholder_container_id = placeholder.container_id
    return placeholder


@router.get("/", response_model=list[schemas.LocationOut])
def list_locations(db: Session = Depends(get_db)):
    return db.query(models.Location).order_by(models.Location.name).all()


@router.get("/{location_id}", response_model=schemas.LocationOut)
def get_location(location_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Location, location_id)
    if not obj:
        raise HTTPException(404, "Location not found")
    return obj


@router.post("/", response_model=schemas.LocationOut, status_code=201)
def create_location(payload: schemas.LocationCreate, db: Session = Depends(get_db)):
    obj = models.Location(**payload.model_dump())
    db.add(obj)
    db.flush()
    _create_placeholder(obj, db)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{location_id}", response_model=schemas.LocationOut)
def update_location(location_id: int, payload: schemas.LocationCreate, db: Session = Depends(get_db)):
    obj = db.get(models.Location, location_id)
    if not obj:
        raise HTTPException(404, "Location not found")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{location_id}", status_code=204)
def delete_location(location_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Location, location_id)
    if not obj:
        raise HTTPException(404, "Location not found")
    db.delete(obj)
    db.commit()
