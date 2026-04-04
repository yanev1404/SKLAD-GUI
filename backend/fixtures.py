from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/fixtures", tags=["Fixtures"])


@router.get("/", response_model=list[schemas.FixtureOut])
def list_fixtures(container_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(models.Fixture)
    if container_id is not None:
        q = q.filter(models.Fixture.container_id == container_id)
    return q.order_by(models.Fixture.short_name, models.Fixture.fixture_id).all()


@router.get("/{fixture_id}", response_model=schemas.FixtureOut)
def get_fixture(fixture_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Fixture, fixture_id)
    if not obj:
        raise HTTPException(404, "Fixture not found")
    return obj


@router.post("/", response_model=list[schemas.FixtureOut], status_code=201)
def create_fixture(payload: schemas.FixtureCreate, db: Session = Depends(get_db)):
    """
    Creates `quantity` individual fixture rows, each representing one physical unit.
    Returns list of created fixtures.
    """
    qty = max(1, payload.quantity)
    data = payload.model_dump(exclude={"quantity"})
    created = []
    for _ in range(qty):
        obj = models.Fixture(**data)
        db.add(obj)
        db.flush()
        created.append(obj)
    db.commit()
    for obj in created:
        db.refresh(obj)
    return created


@router.put("/{fixture_id}", response_model=schemas.FixtureOut)
def update_fixture(fixture_id: int, payload: schemas.FixtureCreate, db: Session = Depends(get_db)):
    obj = db.get(models.Fixture, fixture_id)
    if not obj:
        raise HTTPException(404, "Fixture not found")
    data = payload.model_dump(exclude={"quantity"})
    for k, v in data.items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{fixture_id}", status_code=204)
def delete_fixture(fixture_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Fixture, fixture_id)
    if not obj:
        raise HTTPException(404, "Fixture not found")
    db.delete(obj)
    db.commit()


@router.post("/{fixture_id}/status", response_model=schemas.FixtureOut)
def change_fixture_status(
    fixture_id: int,
    payload: schemas.StatusChangeRequest,
    db: Session = Depends(get_db)
):
    obj = db.get(models.Fixture, fixture_id)
    if not obj:
        raise HTTPException(404, "Fixture not found")
    new_status = db.get(models.Status, payload.new_status_id)
    if not new_status:
        raise HTTPException(404, "Status not found")
    log = models.StatusChangeLog(
        entity_type="fixture", entity_id=fixture_id,
        old_status_id=obj.status_id, new_status_id=payload.new_status_id,
        note=payload.note
    )
    obj.status_id = payload.new_status_id
    db.add(log)
    db.commit()
    db.refresh(obj)
    return obj
