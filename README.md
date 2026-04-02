# Warehouse Inventory Management System

A self-hosted, desktop-local inventory system for managing stage fixtures and transport containers across multiple locations. Tracks equipment packed into containers, supports load operations with barcode scanner input, and maintains a full audit trail of every status change.

---

## What It Does

- Manages a database of **fixtures** (lighting, rigging, and other stage equipment) stored inside **containers** at **locations**
- Tracks **contacts** associated with locations
- Supports **"Pack a Load"** operations: select a group of containers by list or barcode scan, review and deselect individual fixtures, move everything to a destination location, and generate a live manifest with total weight and volume
- Maintains **full audit logging** of every status change, whether triggered by a load or made manually
- Supports **Storno** (sequential undo) of the most recent completed load
- Each location has an auto-generated **placeholder container** to hold deselected items during load operations
- All statuses are **user-managed**: add or delete free-text statuses at any time

---

## Architecture

```
Windows 10
│
├── PostgreSQL (local)          ← single source of truth
│   └── warehouse_db
│
├── pgAdmin 4                   ← Phase 1 admin / data entry
│
└── Python + FastAPI            ← backend API (localhost:8000)
    └── /docs                   ← interactive Swagger UI (use this now)
        
    Phase 2 (planned):
    └── React frontend          ← localhost:3000
```

The FastAPI layer is built now so that the React frontend in Phase 2 can plug straight in — no backend changes needed.

---

## Database Structure

### Core Tables

| Table | Purpose |
|---|---|
| `statuses` | User-managed status list (appendable, deletable) |
| `contacts` | Companies and people linked to locations |
| `locations` | Warehouses, venues, depots, workshops |
| `containers` | Physical transport cases at a location |
| `fixtures` | Individual equipment items inside containers |

### Load & Audit Tables

| Table | Purpose |
|---|---|
| `loads` | One record per completed or stornoed load operation |
| `load_containers` | Which containers were on each load |
| `load_fixtures` | Which fixtures were on each load, with included/deselected flag |
| `load_log` | Lifecycle events per load (created, completed, storno) |
| `status_change_log` | Full audit trail — every status change ever made |

### Key Relationships

```
contacts
  └── locations
        ├── placeholder_container (auto-created)
        └── containers
              └── fixtures

loads
  ├── load_containers → containers
  ├── load_fixtures   → fixtures
  └── load_log

status_change_log → fixtures / containers (any manual or load-driven change)
```

### Fixture Fields

`fixture_id`, `category`, `subcategory`, `short_name`, `quantity`, `manufacturer`, `model`, `weight_kg`, `power_w`, `container_id`, `status_id`, `note`

DMX addresses, RDM UIDs, network info, and serial numbers are stored as free text in the `note` field.

### Container Fields

`container_id`, `category`, `container_type`, `short_name`, `location_id`, `weight_kg`, `width_cm`, `depth_cm`, `height_cm`, `status_id`, `note`

### Default Statuses (seeded, user-editable)

| Status | Meaning |
|---|---|
| `in storage` | At home location, not assigned to a load |
| `packed` | In a container assigned to a completed load |
| `in transit` | Dispatched, physically on the move |
| `on location` | Deployed at an event or external site |
| `in repair` | With a service provider or flagged for repair |
| `retired` | Written off, no longer in active inventory |

---

## Project Structure

```
warehouse/
│
├── db/
│   └── schema.sql              ← Full PostgreSQL schema + seed data
│
├── backend/
│   ├── main.py                 ← FastAPI app entry point
│   ├── config.py               ← Settings loaded from .env
│   ├── database.py             ← SQLAlchemy engine + session
│   ├── models.py               ← ORM table definitions
│   ├── schemas.py              ← Pydantic request/response models
│   └── routers/
│       ├── statuses.py         ← GET / POST / DELETE statuses
│       ├── contacts.py         ← CRUD contacts
│       ├── locations.py        ← CRUD locations + auto placeholder
│       ├── containers.py       ← CRUD + barcode lookup + status change
│       ├── fixtures.py         ← CRUD + status change
│       └── loads.py            ← Pack workflow, manifest, storno
│
├── .env.example                ← Copy to .env and fill in credentials
├── .gitignore
├── start_server.bat            ← Double-click to start the API on Windows
└── README.md
```

---

## Setup

### Prerequisites

- PostgreSQL 15+ installed and running locally
- pgAdmin 4 installed
- Python 3.11+ installed

---

### 1. Clone the repository

```bat
git clone https://github.com/avlasarev/warehouse.git
cd warehouse
```

---

### 2. Create the database

Open pgAdmin 4, connect to your local PostgreSQL server, and run:

```sql
CREATE DATABASE warehouse_db;
```

Then open a terminal and apply the schema:

```bat
psql -U postgres -d warehouse_db -f db/schema.sql
```

This creates all tables, indexes, views, seeds default statuses, and creates the default warehouse location (`WH-MAIN`) with its placeholder container.

---

### 3. Set up the Python environment

```bat
cd warehouse
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
```

---

### 4. Configure credentials

Copy `.env.example` to `.env` and fill in your PostgreSQL password:

```bat
copy .env.example .env
```

Edit `.env`:

```
DB_HOST=localhost
DB_PORT=5432
DB_NAME=warehouse_db
DB_USER=postgres
DB_PASS=your_actual_password
```

> `.env` is listed in `.gitignore` — it will never be committed.

---

### 5. Start the API server

Double-click `start_server.bat`, or run from the terminal:

```bat
.venv\Scripts\activate
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

The API is now running at `http://localhost:8000`

---

## Using the API (Phase 1)

Open your browser and go to:

```
http://localhost:8000/docs
```

This is the **Swagger UI** — a fully interactive interface where you can create, read, update, and delete records across all tables without writing any code. Use this for data entry while the React frontend is in development.

### Recommended data entry order

Enter data in this sequence to satisfy foreign key dependencies:

1. **Statuses** — confirm defaults or add custom ones
2. **Contacts** — companies and people
3. **Locations** — each location automatically gets a placeholder container on creation
4. **Containers** — assign to a location and status
5. **Fixtures** — assign to a container and status

---

## Pack a Load (Workflow)

### Step-by-step

1. In `/docs`, open **POST /loads/**
2. Provide:
   - `origin_location_id` — where the containers currently are
   - `destination_location_id` — where they are going
   - `container_ids` — list of container IDs to include (entered manually or via barcode scan in Phase 2)
   - `deselected_fixture_ids` — fixture IDs to leave behind (they move to the origin placeholder container)
   - `note` — optional

3. On submission:
   - All selected containers move to the destination location with status `packed`
   - All included fixtures update to status `packed`
   - Deselected fixtures move to the origin placeholder container (status unchanged)
   - A load record is created with a full manifest
   - Every status change is written to `status_change_log`

### View the load manifest

```
GET /loads/{load_id}/manifest
```

Returns: all containers, their fixtures (with included/excluded flag), total packed weight (kg), and total volume (m³).

### Barcode scanner

Container barcodes encode the numeric `container_id` only. The scanner acts as a keyboard — scanning a barcode sends the number followed by Enter, which maps directly to:

```
GET /containers/{container_id}
```

This returns the container and all its fixtures, ready to display in the load form. Additional human-readable text on the label is purely for printing and is ignored by the system.

---

## Storno (Undo a Load)

Only the **most recently completed load** can be stornoed, and only sequentially.

```
POST /loads/{load_id}/storno
```

This will:
- Restore each container and fixture to its previous status (read from `status_change_log`)
- Move containers back to the origin location
- Mark the load as `storno` in the database
- Write a `storno_completed` entry to `load_log`

The audit trail is always append-only — storno does not delete any log records.

---

## Useful API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| GET | `/statuses` | List all statuses |
| POST | `/statuses` | Add a new status |
| DELETE | `/statuses/{id}` | Delete a status (blocked if in use) |
| GET | `/locations` | List all locations |
| POST | `/locations` | Create location + auto placeholder |
| GET | `/containers/{id}` | Get container + fixtures (barcode lookup) |
| POST | `/containers/{id}/status` | Manual status change (logged) |
| POST | `/fixtures/{id}/status` | Manual status change (logged) |
| POST | `/loads` | Create and complete a load |
| GET | `/loads/{id}/manifest` | Live load manifest report |
| POST | `/loads/{id}/storno` | Undo the most recent load |

---

## Views (available in pgAdmin)

| View | Description |
|---|---|
| `v_fixtures_full` | All fixtures with container, location, and status |
| `v_container_summary` | Containers with tare weight, fixture weight, volume, and counts |
| `v_load_manifest` | All containers and fixtures per load |

Query directly in pgAdmin's query tool for quick inspection.

---

## Roadmap

- [x] PostgreSQL schema with full audit logging
- [x] FastAPI backend — CRUD for all entities
- [x] Pack a Load workflow with deselection and placeholder logic
- [x] Load manifest with weight and volume totals
- [x] Storno (sequential load undo)
- [x] Manual status change with audit log
- [ ] CSV import for bulk fixture / container entry from Excel
- [ ] React frontend — data entry forms
- [ ] React frontend — Pack a Load form with barcode scanner input
- [ ] React frontend — live manifest report view
- [ ] React frontend — Storno UI
- [ ] Windows Service wrapper for auto-start on boot

---

## Notes

- The `status_change_log` table is append-only. Do not delete rows from it — it is the system's complete history.
- Placeholder containers are created automatically when a location is created. Their `container_type` is `placeholder`. Do not delete them manually.
- All timestamps are stored in UTC (`TIMESTAMPTZ`).
- The `.env` file must never be committed to git. It is excluded by `.gitignore`.

---

## License

Internal use — not for public distribution.
