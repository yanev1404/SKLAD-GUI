from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/loads", tags=["Loads"])


def _get_status_id(name: str, db: Session) -> int:
    s = db.query(models.Status).filter(models.Status.name == name).first()
    if not s:
        raise HTTPException(500, f"Required status '{name}' not found in DB")
    return s.status_id


def _log_load(load_id: int, action: str, note: str | None, db: Session):
    db.add(models.LoadLog(load_id=load_id, action=action, note=note))


def _log_status(entity_type, entity_id, old_id, new_id, load_id, db: Session):
    db.add(models.StatusChangeLog(
        entity_type=entity_type, entity_id=entity_id,
        old_status_id=old_id, new_status_id=new_id, load_id=load_id
    ))


@router.get("/", response_model=list[schemas.LoadOut])
def list_loads(db: Session = Depends(get_db)):
    return db.query(models.Load).order_by(models.Load.created_at.desc()).all()


@router.get("/{load_id}", response_model=schemas.LoadOut)
def get_load(load_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Load, load_id)
    if not obj:
        raise HTTPException(404, "Load not found")
    return obj


@router.get("/{load_id}/manifest", response_model=schemas.LoadManifest)
def get_manifest(load_id: int, db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload
    load = (db.query(models.Load)
        .options(
            joinedload(models.Load.containers).joinedload(models.LoadContainer.container)
                .joinedload(models.Container.fixtures)
                .joinedload(models.Fixture.fixture_model)
        )
        .filter(models.Load.load_id == load_id)
        .first()
    )
    if not load:
        raise HTTPException(404, "Load not found")

    origin = db.get(models.Location, load.origin_location_id)
    dest   = db.get(models.Location, load.destination_location_id)
    lf_map = {lf.fixture_id: lf.included for lf in load.fixtures}

    containers_out = []
    total_weight = 0.0
    total_volume = 0.0

    for lc in load.containers:
        c = lc.container
        tare = float(c.weight_kg or 0)
        vol  = float(c.width_cm * c.depth_cm * c.height_cm) / 1_000_000 \
               if c.width_cm and c.depth_cm and c.height_cm else 0.0

        fixtures_out = []
        fx_weight    = 0.0
        for f in c.fixtures:
            included = lf_map.get(f.fixture_id, True)
            m = f.fixture_model  # joined via relationship
            m_weight = float(m.weight_kg) if m and m.weight_kg else 0.0
            if included:
                fx_weight += m_weight
            fixtures_out.append(schemas.ManifestFixture(
                fixture_id=f.fixture_id,
                model_name=m.model_name if m else (f.short_name if hasattr(f, 'short_name') else '—'),
                weight_kg=m_weight or None,
                included=included
            ))

        total_weight += tare + fx_weight
        total_volume += vol
        containers_out.append(schemas.ManifestContainer(
            container_id=c.container_id,
            short_name=c.short_name,
            tare_kg=tare or None,
            volume_m3=vol or None,
            fixtures=fixtures_out
        ))

    return schemas.LoadManifest(
        load_id=load_id, created_at=load.created_at,
        origin=origin.short_name if origin else "?",
        destination=dest.short_name if dest else "?",
        containers=containers_out,
        total_weight_kg=round(total_weight, 2),
        total_volume_m3=round(total_volume, 4)
    )


@router.post("/", response_model=schemas.LoadOut, status_code=201)
def create_load(payload: schemas.LoadCreate, db: Session = Depends(get_db)):
    """
    Pack a load:
    - Destination type 'warehouse' → fixtures become 'in storage'
    - Otherwise → 'in transit'
    - Deselected fixtures move to origin placeholder container, status unchanged
    - All moves logged in status_change_log
    """
    dest = db.get(models.Location, payload.destination_location_id)
    if not dest:
        raise HTTPException(404, "Destination location not found")
    origin = db.get(models.Location, payload.origin_location_id)
    if not origin:
        raise HTTPException(404, "Origin location not found")

    dest_type = (dest.type or "").lower()
    target_status_name = "in storage" if "warehouse" in dest_type else "in transit"
    target_status_id   = _get_status_id(target_status_name, db)

    placeholder_id = origin.placeholder_container_id
    if not placeholder_id:
        raise HTTPException(500, f"Origin '{origin.short_name}' has no placeholder container")

    load = models.Load(
        origin_location_id=      payload.origin_location_id,
        destination_location_id= payload.destination_location_id,
        event_id=                payload.event_id,
        status="completed",
        note=payload.note
    )
    db.add(load)
    db.flush()
    _log_load(load.load_id, "created", payload.note, db)

    deselected = set(payload.deselected_fixture_ids)

    for cid in payload.container_ids:
        container = db.get(models.Container, cid)
        if not container:
            raise HTTPException(404, f"Container {cid} not found")

        db.add(models.LoadContainer(load_id=load.load_id, container_id=cid))

        # Move container to destination (no status on containers)
        container.location_id = payload.destination_location_id

        # Handle fixtures
        for fixture in container.fixtures:
            included = fixture.fixture_id not in deselected
            db.add(models.LoadFixture(
                load_id=load.load_id, fixture_id=fixture.fixture_id, included=included
            ))
            old_status = fixture.status_id
            if included:
                fixture.status_id = target_status_id
                _log_status("fixture", fixture.fixture_id, old_status, target_status_id, load.load_id, db)
            else:
                # Deselected: move to placeholder, status unchanged
                fixture.container_id = placeholder_id
                _log_status("fixture", fixture.fixture_id, old_status, old_status, load.load_id, db)

    _log_load(load.load_id, "completed", None, db)
    db.commit()
    db.refresh(load)
    return load


@router.post("/{load_id}/storno", response_model=schemas.LoadOut)
def storno_load(load_id: int, db: Session = Depends(get_db)):
    from sqlalchemy.orm import joinedload
    load = (db.query(models.Load)
        .options(
            joinedload(models.Load.containers).joinedload(models.LoadContainer.container)
                .joinedload(models.Container.fixtures)
                .joinedload(models.Fixture.fixture_model)
        )
        .filter(models.Load.load_id == load_id)
        .first()
    )
    if not load:
        raise HTTPException(404, "Load not found")
    if load.status == "storno":
        raise HTTPException(409, "Load is already stornoed")

    latest = (
        db.query(models.Load)
        .filter(models.Load.status == "completed")
        .order_by(models.Load.created_at.desc())
        .first()
    )
    if not latest or latest.load_id != load_id:
        raise HTTPException(409, "Only the most recent completed load can be stornoed")

    _log_load(load_id, "storno_initiated", None, db)

    for lc in load.containers:
        container = lc.container
        container.location_id = load.origin_location_id

    for lf in load.fixtures:
        fixture = lf.fixture
        prev = (
            db.query(models.StatusChangeLog)
            .filter(
                models.StatusChangeLog.entity_type == "fixture",
                models.StatusChangeLog.entity_id   == fixture.fixture_id,
                models.StatusChangeLog.load_id     == load_id
            ).first()
        )
        if prev:
            fixture.status_id = prev.old_status_id

    load.status = "storno"
    _log_load(load_id, "storno_completed", None, db)
    db.commit()
    db.refresh(load)
    return load
