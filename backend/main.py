from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from .routers import statuses, contacts, locations, containers, fixtures, loads

app = FastAPI(
    title="Warehouse Management API",
    description="Backend for fixture and container inventory management.",
    version="1.0.0"
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


@app.get("/", tags=["Health"])
def root():
    return {
        "status": "ok",
        "ui": "http://localhost:8000/app",
        "docs": "http://localhost:8000/docs"
    }


# Serve the frontend — mounted last so API routes take priority
_frontend = os.path.join(os.path.dirname(__file__), "..", "frontend")
if os.path.isdir(_frontend):
    app.mount("/app", StaticFiles(directory=_frontend, html=True), name="frontend")
