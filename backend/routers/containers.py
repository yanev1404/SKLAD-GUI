from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/containers", tags=["Containers"])


@router.get("/", response_model=list[schemas.ContainerOut])
def list_containers(location_id: int | None = None, db: Session = Depends(get_db)):
    q = db.query(models.Container)
    if location_id:
        q = q.filter(models.Container.location_id == location_id)
    return q.order_by(models.Container.short_name).all()


@router.get("/{container_id}", response_model=schemas.ContainerWithFixtures)
def get_container(container_id: int, db: Session = Depends(get_db)):
    """Fetch container + all its fixtures. Used by barcode scanner lookup."""
    obj = (
        db.query(models.Container)
        .options(joinedload(models.Container.fixtures))
        .filter(models.Container.container_id == container_id)
        .first()
    )
    if not obj:
        raise HTTPException(404, f"Container {container_id} not found")
    return obj


@router.post("/", response_model=schemas.ContainerOut, status_code=201)
def create_container(payload: schemas.ContainerCreate, db: Session = Depends(get_db)):
    obj = models.Container(**payload.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/{container_id}", response_model=schemas.ContainerOut)
def update_container(container_id: int, payload: schemas.ContainerCreate, db: Session = Depends(get_db)):
    obj = db.get(models.Container, container_id)
    if not obj:
        raise HTTPException(404, "Container not found")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{container_id}", status_code=204)
def delete_container(container_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Container, container_id)
    if not obj:
        raise HTTPException(404, "Container not found")
    if obj.container_type == "placeholder":
        raise HTTPException(409, "Cannot delete a placeholder container directly")
    db.delete(obj)
    db.commit()


@router.post("/{container_id}/status", response_model=schemas.ContainerOut)
def change_container_status(
    container_id: int,
    payload: schemas.StatusChangeRequest,
    db: Session = Depends(get_db)
):
    """Manual status change with audit log entry."""
    obj = db.get(models.Container, container_id)
    if not obj:
        raise HTTPException(404, "Container not found")
    new_status = db.get(models.Status, payload.new_status_id)
    if not new_status:
        raise HTTPException(404, "Status not found")

    log = models.StatusChangeLog(
        entity_type=   "container",
        entity_id=     container_id,
        old_status_id= obj.status_id,
        new_status_id= payload.new_status_id,
        note=          payload.note
    )
    obj.status_id = payload.new_status_id
    db.add(log)
    db.commit()
    db.refresh(obj)
    return obj
