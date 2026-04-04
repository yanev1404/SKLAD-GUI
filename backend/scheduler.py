"""
Event status scheduler.
Runs every 60 seconds. Handles:
  - Event start: fixtures/containers → 'on location', timestamped at event start_date
  - Event end:   fixtures/containers → 'packed', timestamped at event end_date
  - Catchup on server restart for both missed starts and missed ends
"""
import asyncio
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from . import models
from .database import SessionLocal

log = logging.getLogger("scheduler")


def _get_status_id(name: str, db: Session) -> int | None:
    s = db.query(models.Status).filter(models.Status.name == name).first()
    return s.status_id if s else None


def _log_status(entity_type, entity_id, old_id, new_id, load_id, ts, db):
    db.add(models.StatusChangeLog(
        entity_type=entity_type,
        entity_id=entity_id,
        old_status_id=old_id,
        new_status_id=new_id,
        load_id=load_id,
        timestamp=ts
    ))


def _apply_event_start(load: models.Load, db: Session):
    """Set all fixtures/containers on this load to 'on location'."""
    on_loc_id = _get_status_id("on location", db)
    if not on_loc_id:
        return
    ts = load.event.start_date if load.event and load.event.start_date else datetime.now(timezone.utc)

    for lc in load.containers:
        c = lc.container
        old = c.status_id
        c.status_id = on_loc_id
        _log_status("container", c.container_id, old, on_loc_id, load.load_id, ts, db)

    for lf in load.fixtures:
        if not lf.included:
            continue
        f = lf.fixture
        old = f.status_id
        f.status_id = on_loc_id
        _log_status("fixture", f.fixture_id, old, on_loc_id, load.load_id, ts, db)

    load.event_activated = True
    db.add(models.LoadLog(load_id=load.load_id, timestamp=ts,
                          action="event_activated",
                          note=f"Auto-activated by scheduler"))


def _apply_event_end(load: models.Load, db: Session):
    """Set all fixtures/containers on this load to 'packed'."""
    packed_id = _get_status_id("packed", db)
    if not packed_id:
        return
    ts = load.event.end_date if load.event and load.event.end_date else datetime.now(timezone.utc)

    for lc in load.containers:
        c = lc.container
        old = c.status_id
        c.status_id = packed_id
        _log_status("container", c.container_id, old, packed_id, load.load_id, ts, db)

    for lf in load.fixtures:
        if not lf.included:
            continue
        f = lf.fixture
        old = f.status_id
        f.status_id = packed_id
        _log_status("fixture", f.fixture_id, old, packed_id, load.load_id, ts, db)

    load.event_ended = True
    db.add(models.LoadLog(load_id=load.load_id, timestamp=ts,
                          action="event_ended",
                          note="Auto-ended by scheduler"))


def run_scheduler_tick():
    """Single scheduler tick — run in a thread to avoid blocking the event loop."""
    db: Session = SessionLocal()
    try:
        now = datetime.now(timezone.utc)

        # Find all completed loads linked to an event
        loads = (
            db.query(models.Load)
            .join(models.Event, models.Load.event_id == models.Event.event_id)
            .filter(models.Load.status == "completed")
            .all()
        )

        for load in loads:
            ev = load.event
            if not ev:
                continue

            # ── Catchup / normal: event has started, not yet activated ──
            if ev.start_date and ev.start_date <= now and not load.event_activated:
                log.info(f"Activating load {load.load_id} (event {ev.short_name})")
                _apply_event_start(load, db)

            # ── Catchup / normal: event has ended, not yet ended ──
            if ev.end_date and ev.end_date <= now and load.event_activated and not load.event_ended:
                log.info(f"Ending load {load.load_id} (event {ev.short_name})")
                _apply_event_end(load, db)

        db.commit()
    except Exception as e:
        log.error(f"Scheduler error: {e}")
        db.rollback()
    finally:
        db.close()


async def start_scheduler():
    """Asyncio background task — runs every 60 seconds."""
    log.info("Event scheduler started")
    while True:
        try:
            await asyncio.get_event_loop().run_in_executor(None, run_scheduler_tick)
        except Exception as e:
            log.error(f"Scheduler loop error: {e}")
        await asyncio.sleep(60)
