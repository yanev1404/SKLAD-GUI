import os, uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from .. import models as db_models, schemas
from ..database import get_db

router = APIRouter(prefix="/fixtures", tags=["Fixtures"])

FILES_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'db', 'files')
MAX_FILE_MB = 20
ALLOWED_MIME = {'application/pdf', 'image/png', 'image/jpeg', 'image/webp'}
os.makedirs(FILES_DIR, exist_ok=True)


def _enrich(fx: db_models.Fixture) -> dict:
    """Return fixture + flattened model fields as a plain dict."""
    m = fx.fixture_model  # pre-loaded via joinedload
    return {
        "fixture_id":   fx.fixture_id,
        "short_name":   fx.short_name,
        "model_id":     fx.model_id,
        "container_id": fx.container_id,
        "status_id":    fx.status_id,
        "note":         fx.note,
        "model_name":   m.model_name   if m else None,
        "category":     m.category     if m else None,
        "subcategory":  m.subcategory  if m else None,
        "manufacturer": m.manufacturer if m else None,
        "model":        m.model        if m else None,
        "weight_kg":    float(m.weight_kg) if m and m.weight_kg is not None else None,
        "power_w":      float(m.power_w)   if m and m.power_w   is not None else None,
    }


def _q(db: Session):
    """Base query with fixture_model eagerly loaded."""
    return db.query(db_models.Fixture).options(
        joinedload(db_models.Fixture.fixture_model)
    )


@router.get("/", response_model=list[schemas.FixtureOut])
def list_fixtures(container_id: int | None = None, db: Session = Depends(get_db)):
    q = _q(db)
    if container_id is not None:
        q = q.filter(db_models.Fixture.container_id == container_id)
    return [_enrich(f) for f in q.order_by(db_models.Fixture.fixture_id).all()]


@router.get("/{fixture_id}", response_model=schemas.FixtureOut)
def get_fixture(fixture_id: int, db: Session = Depends(get_db)):
    obj = _q(db).filter(db_models.Fixture.fixture_id == fixture_id).first()
    if not obj:
        raise HTTPException(404, "Fixture not found")
    return _enrich(obj)


@router.post("/", response_model=list[schemas.FixtureOut], status_code=201)
def create_fixture(payload: schemas.FixtureCreate, db: Session = Depends(get_db)):
    qty = max(1, payload.quantity)
    data = payload.model_dump(exclude={"quantity"})
    created = []
    for _ in range(qty):
        obj = db_models.Fixture(**data)
        db.add(obj)
        db.flush()
        created.append(obj)
    db.commit()
    ids = [o.fixture_id for o in created]
    enriched = _q(db).filter(
        db_models.Fixture.fixture_id.in_(ids)
    ).order_by(db_models.Fixture.fixture_id).all()
    return [_enrich(f) for f in enriched]


@router.put("/{fixture_id}", response_model=schemas.FixtureOut)
def update_fixture(fixture_id: int, payload: schemas.FixtureCreate, db: Session = Depends(get_db)):
    obj = db.get(db_models.Fixture, fixture_id)
    if not obj:
        raise HTTPException(404, "Fixture not found")
    for k, v in payload.model_dump(exclude={"quantity"}).items():
        setattr(obj, k, v)
    db.commit()
    obj = _q(db).filter(db_models.Fixture.fixture_id == fixture_id).first()
    return _enrich(obj)


@router.put("/upsert/{fixture_id}", response_model=schemas.FixtureOut)
def upsert_fixture(fixture_id: int, payload: schemas.FixtureCreate, db: Session = Depends(get_db)):
    obj = db.get(db_models.Fixture, fixture_id)
    data = payload.model_dump(exclude={"quantity"})
    if obj:
        for k, v in data.items():
            setattr(obj, k, v)
    else:
        obj = db_models.Fixture(fixture_id=fixture_id, **data)
        db.add(obj)
    db.commit()
    obj = _q(db).filter(db_models.Fixture.fixture_id == fixture_id).first()
    return _enrich(obj)


@router.delete("/{fixture_id}", status_code=204)
def delete_fixture(fixture_id: int, db: Session = Depends(get_db)):
    obj = db.get(db_models.Fixture, fixture_id)
    if not obj:
        raise HTTPException(404, "Fixture not found")
    db.delete(obj)
    db.commit()


@router.post("/{fixture_id}/status", response_model=schemas.FixtureOut)
def change_fixture_status(fixture_id: int, payload: schemas.StatusChangeRequest, db: Session = Depends(get_db)):
    obj = db.get(db_models.Fixture, fixture_id)
    if not obj:
        raise HTTPException(404, "Fixture not found")
    new_status = db.get(db_models.Status, payload.new_status_id)
    if not new_status:
        raise HTTPException(404, "Status not found")
    log = db_models.StatusChangeLog(
        entity_type="fixture", entity_id=fixture_id,
        old_status_id=obj.status_id, new_status_id=payload.new_status_id,
        note=payload.note
    )
    obj.status_id = payload.new_status_id
    db.add(log)
    db.commit()
    obj = _q(db).filter(db_models.Fixture.fixture_id == fixture_id).first()
    return _enrich(obj)


# ── Per-fixture file attachments ──────────────────────────────
@router.get("/{fixture_id}/files", response_model=list[schemas.FileOut])
def list_fixture_files(fixture_id: int, db: Session = Depends(get_db)):
    obj = db.get(db_models.Fixture, fixture_id)
    if not obj:
        raise HTTPException(404, "Fixture not found")
    return obj.files


@router.post("/{fixture_id}/files", response_model=schemas.FileOut, status_code=201)
async def upload_fixture_file(
    fixture_id: int,
    file: UploadFile = File(...),
    note: str = Form(default=''),
    db: Session = Depends(get_db)
):
    obj = db.get(db_models.Fixture, fixture_id)
    if not obj:
        raise HTTPException(404, "Fixture not found")
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(400, "Allowed types: PDF, PNG, JPEG, WebP")
    content = await file.read()
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {MAX_FILE_MB}MB")
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'bin'
    fname = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(FILES_DIR, fname), 'wb') as f:
        f.write(content)
    rec = db_models.FixtureFile(
        fixture_id=fixture_id, filename=fname,
        original_name=file.filename, mime_type=file.content_type,
        size_bytes=len(content), note=note or None
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.get("/{fixture_id}/files/{file_id}/download")
def download_fixture_file(fixture_id: int, file_id: int, db: Session = Depends(get_db)):
    rec = db.query(db_models.FixtureFile).filter_by(
        file_id=file_id, fixture_id=fixture_id
    ).first()
    if not rec:
        raise HTTPException(404, "File not found")
    path = os.path.join(FILES_DIR, rec.filename)
    if not os.path.exists(path):
        raise HTTPException(404, "File missing from disk")
    return FileResponse(path, filename=rec.original_name, media_type=rec.mime_type)


@router.delete("/{fixture_id}/files/{file_id}", status_code=204)
def delete_fixture_file(fixture_id: int, file_id: int, db: Session = Depends(get_db)):
    rec = db.query(db_models.FixtureFile).filter_by(
        file_id=file_id, fixture_id=fixture_id
    ).first()
    if not rec:
        raise HTTPException(404, "File not found")
    path = os.path.join(FILES_DIR, rec.filename)
    if os.path.exists(path):
        os.remove(path)
    db.delete(rec)
    db.commit()
