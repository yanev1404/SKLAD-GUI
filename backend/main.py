import asyncio
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager

from .routers import statuses, contacts, locations, containers, fixtures, loads, events, fixture_models
from .scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run one immediate tick on startup (catchup), then schedule every 60s
    task = asyncio.create_task(start_scheduler())
    yield
    task.cancel()


app = FastAPI(
    title="Warehouse Management API",
    description="Backend for fixture and container inventory management.",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000", "http://127.0.0.1:8000",
        "http://localhost:3000", "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(statuses.router)
app.include_router(contacts.router)
app.include_router(locations.router)
app.include_router(containers.router)
app.include_router(fixtures.router)
app.include_router(loads.router)
app.include_router(events.router)
app.include_router(fixture_models.router)


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "ok",
        "ui": "http://localhost:8000/app",
        "docs": "http://localhost:8000/docs"
    }

@app.get("/debug/fixtures", tags=["Debug"])
def debug_fixtures(db = __import__("fastapi", fromlist=["Depends"]).Depends(__import__("backend.database", fromlist=["get_db"]).get_db)):
    pass

@app.get("/debug/test", tags=["Debug"])
def debug_test():
    try:
        from .database import SessionLocal
        from . import models as m
        from sqlalchemy.orm import joinedload
        db = SessionLocal()
        try:
            # Step 1: basic query
            fx_count = db.query(m.Fixture).count()
            # Step 2: access short_name on first fixture
            fx = db.query(m.Fixture).first()
            sn = fx.short_name if fx else "no fixtures"
            # Step 3: joinedload
            fx2 = db.query(m.Fixture).options(joinedload(m.Fixture.fixture_model)).first()
            model_name = fx2.fixture_model.model_name if fx2 and fx2.fixture_model else "no model"
            return {"count": fx_count, "first_short_name": sn, "first_model_name": model_name}
        except Exception as e:
            return {"error": str(e), "type": type(e).__name__}
        finally:
            db.close()
    except Exception as e:
        return {"import_error": str(e)}


_frontend = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_frontend):
    app.mount("/app", StaticFiles(directory=_frontend, html=True), name="frontend")
