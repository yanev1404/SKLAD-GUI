from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/loads", tags=["Loads"])


def _get_status_id(name: str, db: Session) -> int:
    s = db.query(models.Status).filter(models.Status.name == name).first()
    if not s:
        raise HTTPException(500, f"Required status '{name}' not found in DB")
    return s.status_id

def _get_status_id_soft(name: str, db: Session) -> int | None:
    s = db.query(models.Status).filter(models.Status.name == name).first()
    return s.status_id if s else None

def _log_load(load_id: int, action: str, note: str | None, db: Session):
    db.add(models.LoadLog(load_id=load_id, action=action, note=note))

def _log_status(entity_type, entity_id, old_id, new_id, load_id, db: Session):
    db.add(models.StatusChangeLog(
        entity_type=entity_type,
        entity_id=entity_id,
        old_status_id=old_id,
        new_status_id=new_id,
        load_id=load_id
    ))


# ── List loads ────────────────────────────────────────────────
@router.get("/", response_model=list[schemas.LoadOut])
def list_loads(db: Session = Depends(get_db)):
    return db.query(models.Load).order_by(models.Load.created_at.desc()).all()


# ── Get load ──────────────────────────────────────────────────
@router.get("/{load_id}", response_model=schemas.LoadOut)
def get_load(load_id: int, db: Session = Depends(get_db)):
    obj = db.get(models.Load, load_id)
    if not obj:
        raise HTTPException(404, "Load not found")
    return obj


# ── Load manifest ─────────────────────────────────────────────
@router.get("/{load_id}/manifest", response_model=schemas.LoadManifest)
def get_manifest(load_id: int, db: Session = Depends(get_db)):
    load = db.get(models.Load, load_id)
    if not load:
        raise HTTPException(404, "Load not found")

    origin = db.get(models.Location, load.origin_location_id)
    dest   = db.get(models.Location, load.destination_location_id)
    lf_rows = {lf.fixture_id: lf.included for lf in load.fixtures}

    containers_out = []
    total_weight = 0.0
    total_volume = 0.0

    for lc in load.containers:
        c = lc.container
        tare = float(c.weight_kg or 0)
        vol  = 0.0
        if c.width_cm and c.depth_cm and c.height_cm:
            vol = float(c.width_cm * c.depth_cm * c.height_cm) / 1_000_000

        fixtures_out = []
        fixtures_weight = 0.0
        for f in c.fixtures:
            included = lf_rows.get(f.fixture_id, True)
            fw = float(f.weight_kg or 0) * float(f.quantity or 1)
            if included:
                fixtures_weight += fw
            fixtures_out.append(schemas.ManifestFixture(
                fixture_id=f.fixture_id,
                short_name=f.short_name,
                quantity=f.quantity,
                weight_kg=float(f.weight_kg) if f.weight_kg else None,
                included=included
            ))

        container_total = tare + fixtures_weight
        total_weight   += container_total
        total_volume   += vol

        containers_out.append(schemas.ManifestContainer(
            container_id=c.container_id,
            short_name=c.short_name,
            tare_kg=tare or None,
            volume_m3=vol or None,
            fixtures=fixtures_out
        ))

    return schemas.LoadManifest(
        load_id=load_id,
        created_at=load.created_at,
        origin=origin.short_name if origin else "?",
        destination=dest.short_name if dest else "?",
        containers=containers_out,
        total_weight_kg=round(total_weight, 2),
        total_volume_m3=round(total_volume, 4)
    )


# ── Create / pack a load ──────────────────────────────────────
@router.post("/", response_model=schemas.LoadOut, status_code=201)
def create_load(payload: schemas.LoadCreate, db: Session = Depends(get_db)):
    """
    Pack a load:
    - Resolves target status based on destination type:
        warehouse → 'in storage', otherwise → 'in transit'
    - Moves selected containers + included fixtures to destination
    - Deselected fixtures stay in origin placeholder container
    - All status changes logged
    """
    dest = db.get(models.Location, payload.destination_location_id)
    if not dest:
        raise HTTPException(404, "Destination location not found")
    origin = db.get(models.Location, payload.origin_location_id)
    if not origin:
        raise HTTPException(404, "Origin location not found")

    # Determine target status based on destination type
    dest_type = (dest.type or "").lower()
    if "warehouse" in dest_type:
        target_status_name = "in storage"
    else:
        target_status_name = "in transit"

    target_status_id = _get_status_id(target_status_name, db)
    packed_status_id = _get_status_id("packed", db)

    placeholder_id = origin.placeholder_container_id
    if not placeholder_id:
        raise HTTPException(500, f"Origin '{origin.short_name}' has no placeholder container")

    # Validate event if provided
    event_id = getattr(payload, 'event_id', None)
    if event_id:
        ev = db.execute(text("SELECT event_id FROM events WHERE event_id=:id"), {"id": event_id}).first()
        if not ev:
            raise HTTPException(404, "Event not found")

    load = models.Load(
        origin_location_id=payload.origin_location_id,
        destination_location_id=payload.destination_location_id,
        status="completed",
        note=payload.note,
        event_id=event_id
    )
    db.add(load)
    db.flush()

    _log_load(load.load_id, "created", payload.note, db)

    deselected_ids  = set(payload.deselected_fixture_ids)
    # adjusted_qty: {fixture_id: new_qty} for partial quantity removals
    adjusted_qty    = getattr(payload, 'adjusted_quantities', {}) or {}
    # removed_items: [{fixture_id, quantity_removed}] — go to placeholder
    removed_items   = getattr(payload, 'removed_items', []) or []

    for cid in payload.container_ids:
        container = db.get(models.Container, cid)
        if not container:
            raise HTTPException(404, f"Container {cid} not found")

        db.add(models.LoadContainer(load_id=load.load_id, container_id=cid))

        old_c_status = container.status_id
        container.location_id = payload.destination_location_id
        container.status_id   = packed_status_id
        _log_status("container", cid, old_c_status, packed_status_id, load.load_id, db)

        for fixture in container.fixtures:
            included = fixture.fixture_id not in deselected_ids

            db.add(models.LoadFixture(
                load_id=load.load_id,
                fixture_id=fixture.fixture_id,
                included=included
            ))

            old_f_status = fixture.status_id

            if included:
                # Handle partial quantity removal
                qty_removed = 0
                for ri in removed_items:
                    if ri.get('fixture_id') == fixture.fixture_id:
                        qty_removed = ri.get('quantity_removed', 0)
                        break

                if qty_removed > 0:
                    # Move removed qty to placeholder
                    _move_to_placeholder(
                        db, fixture, qty_removed, placeholder_id, load.load_id
                    )
                    fixture.quantity = max(1, fixture.quantity - qty_removed)

                fixture.status_id = target_status_id
                _log_status("fixture", fixture.fixture_id, old_f_status,
                            target_status_id, load.load_id, db)
            else:
                # Fully deselected — move to placeholder
                _move_to_placeholder(
                    db, fixture, fixture.quantity, placeholder_id, load.load_id
                )
                fixture.container_id = placeholder_id
                _log_status("fixture", fixture.fixture_id, old_f_status,
                            old_f_status, load.load_id, db)

    _log_load(load.load_id, "completed", None, db)
    db.commit()
    db.refresh(load)
    return load


def _move_to_placeholder(db, fixture, qty_to_move, placeholder_id, load_id):
    """
    Move qty_to_move units of a fixture to the placeholder container.
    If a fixture of the same model already exists there, increase its quantity.
    Otherwise create a new fixture record.
    """
    if not fixture.model:
        # No model — just create a new entry
        _create_placeholder_fixture(db, fixture, qty_to_move, placeholder_id)
        return

    existing = db.query(models.Fixture).filter(
        models.Fixture.container_id == placeholder_id,
        models.Fixture.model        == fixture.model,
        models.Fixture.manufacturer == fixture.manufacturer
    ).first()

    if existing:
        existing.quantity += qty_to_move
    else:
        _create_placeholder_fixture(db, fixture, qty_to_move, placeholder_id)


def _create_placeholder_fixture(db, source, qty, placeholder_id):
    storage_status = db.query(models.Status).filter(
        models.Status.name == "in storage"
    ).first()
    new_fx = models.Fixture(
        category=     source.category,
        subcategory=  source.subcategory,
        short_name=   source.short_name,
        quantity=     qty,
        manufacturer= source.manufacturer,
        model=        source.model,
        weight_kg=    source.weight_kg,
        power_w=      source.power_w,
        container_id= placeholder_id,
        status_id=    storage_status.status_id if storage_status else None,
        note=         f"Split from fixture {source.fixture_id} during load packing"
    )
    db.add(new_fx)


# ── Storno ────────────────────────────────────────────────────
@router.post("/{load_id}/storno", response_model=schemas.LoadOut)
def storno_load(load_id: int, db: Session = Depends(get_db)):
    load = db.get(models.Load, load_id)
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
        prev_log = (
            db.query(models.StatusChangeLog)
            .filter(
                models.StatusChangeLog.entity_type == "container",
                models.StatusChangeLog.entity_id   == container.container_id,
                models.StatusChangeLog.load_id     == load_id
            ).first()
        )
        if prev_log:
            container.status_id = prev_log.old_status_id
        container.location_id = load.origin_location_id

    for lf in load.fixtures:
        fixture = lf.fixture
        prev_log = (
            db.query(models.StatusChangeLog)
            .filter(
                models.StatusChangeLog.entity_type == "fixture",
                models.StatusChangeLog.entity_id   == fixture.fixture_id,
                models.StatusChangeLog.load_id     == load_id
            ).first()
        )
        if prev_log:
            fixture.status_id = prev_log.old_status_id

    load.status = "storno"
    _log_load(load_id, "storno_completed", None, db)
    db.commit()
    db.refresh(load)
    return load
