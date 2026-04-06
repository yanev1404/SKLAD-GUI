"""
Router for the `models` table (fixture model/product specs).
Separate from fixtures (individual physical units).
"""
import os, uuid, shutil
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from .. import models as db_models, schemas
from ..database import get_db

router = APIRouter(prefix="/fixture-models", tags=["Fixture Models"])

# File storage paths  (relative to project root; created by migration)
BASE_DIR     = os.path.join(os.path.dirname(__file__), '..', '..', 'db')
IMAGES_DIR   = os.path.join(BASE_DIR, 'images')
FILES_DIR    = os.path.join(BASE_DIR, 'files')
MAX_FILE_MB  = 20
ALLOWED_MIME = {'application/pdf', 'image/png', 'image/jpeg', 'image/webp'}

os.makedirs(IMAGES_DIR, exist_ok=True)
os.makedirs(FILES_DIR,  exist_ok=True)


# ── CRUD ─────────────────────────────────────────────────────
@router.get("/", response_model=list[schemas.FixtureModelOut])
def list_models(db: Session = Depends(get_db)):
    return db.query(db_models.FixtureModel).order_by(db_models.FixtureModel.model_name).all()


@router.get("/{model_id}", response_model=schemas.FixtureModelOut)
def get_model(model_id: int, db: Session = Depends(get_db)):
    obj = db.get(db_models.FixtureModel, model_id)
    if not obj:
        raise HTTPException(404, "Model not found")
    return obj


@router.post("/", response_model=schemas.FixtureModelOut, status_code=201)
def create_model(payload: schemas.FixtureModelCreate, db: Session = Depends(get_db)):
    obj = db_models.FixtureModel(**payload.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.put("/{model_id}", response_model=schemas.FixtureModelOut)
def update_model(model_id: int, payload: schemas.FixtureModelCreate, db: Session = Depends(get_db)):
    obj = db.get(db_models.FixtureModel, model_id)
    if not obj:
        raise HTTPException(404, "Model not found")
    for k, v in payload.model_dump().items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/{model_id}", status_code=204)
def delete_model(model_id: int, db: Session = Depends(get_db)):
    obj = db.get(db_models.FixtureModel, model_id)
    if not obj:
        raise HTTPException(404, "Model not found")
    if model_id == 1001:
        raise HTTPException(409, "Cannot delete the DUMMY model")
    # Reassign fixtures to DUMMY
    for fx in obj.fixtures:
        fx.model_id = 1001
    db.delete(obj); db.commit()


# ── Preview image ─────────────────────────────────────────────
@router.post("/{model_id}/preview", response_model=schemas.FixtureModelOut)
async def upload_preview(model_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    obj = db.get(db_models.FixtureModel, model_id)
    if not obj:
        raise HTTPException(404, "Model not found")
    if file.content_type not in {'image/png', 'image/jpeg', 'image/webp'}:
        raise HTTPException(400, "Preview must be PNG, JPEG or WebP")
    content = await file.read()
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {MAX_FILE_MB}MB limit")
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'jpg'
    fname = f"model_{model_id}_preview.{ext}"
    with open(os.path.join(IMAGES_DIR, fname), 'wb') as f:
        f.write(content)
    # Delete old preview file if different name
    if obj.preview_image and obj.preview_image != fname:
        old = os.path.join(IMAGES_DIR, obj.preview_image)
        if os.path.exists(old): os.remove(old)
    obj.preview_image = fname
    db.commit(); db.refresh(obj)
    return obj


@router.get("/{model_id}/preview/image")
def get_preview(model_id: int, db: Session = Depends(get_db)):
    obj = db.get(db_models.FixtureModel, model_id)
    if not obj or not obj.preview_image:
        raise HTTPException(404, "No preview image")
    path = os.path.join(IMAGES_DIR, obj.preview_image)
    if not os.path.exists(path):
        raise HTTPException(404, "Image file not found on disk")
    return FileResponse(path)


@router.post("/{model_id}/preview/auto-assign")
def auto_assign_preview(model_id: int, db: Session = Depends(get_db)):
    """Match a model's model_name to an image filename in db/images/ (case-insensitive)."""
    obj = db.get(db_models.FixtureModel, model_id)
    if not obj:
        raise HTTPException(404, "Model not found")
    name_lower = obj.model_name.lower()
    for fname in os.listdir(IMAGES_DIR):
        base = fname.rsplit('.', 1)[0].lower()
        if base == name_lower:
            obj.preview_image = fname
            db.commit()
            return {"matched": fname}
    return {"matched": None}


@router.post("/preview/auto-assign-all")
def auto_assign_all_previews(db: Session = Depends(get_db)):
    """Scan db/images/ and assign preview to any model whose name matches a filename."""
    image_map = {f.rsplit('.', 1)[0].lower(): f for f in os.listdir(IMAGES_DIR)}
    matched = []
    for mdl in db.query(db_models.FixtureModel).all():
        key = mdl.model_name.lower()
        if key in image_map:
            mdl.preview_image = image_map[key]
            matched.append({'model_id': mdl.model_id, 'model_name': mdl.model_name, 'file': image_map[key]})
    db.commit()
    return {"matched": len(matched), "items": matched}


# ── File attachments ──────────────────────────────────────────
@router.get("/{model_id}/files", response_model=list[schemas.FileOut])
def list_model_files(model_id: int, db: Session = Depends(get_db)):
    obj = db.get(db_models.FixtureModel, model_id)
    if not obj: raise HTTPException(404, "Model not found")
    return obj.files


@router.post("/{model_id}/files", response_model=schemas.FileOut, status_code=201)
async def upload_model_file(
    model_id: int,
    file: UploadFile = File(...),
    note: str = Form(default=''),
    db: Session = Depends(get_db)
):
    obj = db.get(db_models.FixtureModel, model_id)
    if not obj: raise HTTPException(404, "Model not found")
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(400, "Allowed types: PDF, PNG, JPEG, WebP")
    content = await file.read()
    if len(content) > MAX_FILE_MB * 1024 * 1024:
        raise HTTPException(400, f"File exceeds {MAX_FILE_MB}MB")
    ext   = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else 'bin'
    fname = f"{uuid.uuid4().hex}.{ext}"
    with open(os.path.join(FILES_DIR, fname), 'wb') as f:
        f.write(content)
    rec = db_models.ModelFile(
        model_id=model_id, filename=fname, original_name=file.filename,
        mime_type=file.content_type, size_bytes=len(content), note=note or None
    )
    db.add(rec); db.commit(); db.refresh(rec)
    return rec


@router.get("/{model_id}/files/{file_id}/download")
def download_model_file(model_id: int, file_id: int, db: Session = Depends(get_db)):
    rec = db.query(db_models.ModelFile).filter_by(file_id=file_id, model_id=model_id).first()
    if not rec: raise HTTPException(404, "File not found")
    path = os.path.join(FILES_DIR, rec.filename)
    if not os.path.exists(path): raise HTTPException(404, "File missing from disk")
    return FileResponse(path, filename=rec.original_name, media_type=rec.mime_type)


@router.delete("/{model_id}/files/{file_id}", status_code=204)
def delete_model_file(model_id: int, file_id: int, db: Session = Depends(get_db)):
    rec = db.query(db_models.ModelFile).filter_by(file_id=file_id, model_id=model_id).first()
    if not rec: raise HTTPException(404, "File not found")
    path = os.path.join(FILES_DIR, rec.filename)
    if os.path.exists(path): os.remove(path)
    db.delete(rec); db.commit()
