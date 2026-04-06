# SKLAD — Warehouse Management System

**Beta v0.9**

SKLAD is a self-hosted warehouse management service for professional equipment rental operations. It tracks physical inventory — lighting rigs, audio gear, staging equipment, and anything else that ships in flight cases — across its full lifecycle: storage, packing, transport, venue deployment, and return.

The system is built around a relational PostgreSQL database that links individual fixture units to their product models, the containers they travel in, the locations they live at, and the events they're deployed to. Everything is managed through a single browser-based interface with no build step required.

---

## Credits

Inspired by the seed project by **avlasarev**:
[https://github.com/avlasarev/warehouse](https://github.com/avlasarev/warehouse)

---

## Table of Contents

- [Use Case](#use-case)
- [Architecture](#architecture)
- [Data Model](#data-model)
- [Prerequisites](#prerequisites)
- [Building from Scratch](#building-from-scratch)
- [Running the Server](#running-the-server)
- [Daily Operations](#daily-operations)
- [Frontend Tabs](#frontend-tabs)
- [Feature Reference](#feature-reference)
- [API Reference](#api-reference)
- [File Storage](#file-storage)
- [Environment Variables](#environment-variables)

---

## Use Case

Equipment rental companies manage large inventories of identical or near-identical units (e.g. 40 of the same moving head fixture) that must be packed into containers, assigned to loads, transported to venues, tracked during use, and returned. SKLAD provides:

- A **model registry** so specs (weight, dimensions, power draw) are defined once and shared across all units of that type
- A **fixture registry** for individual serialised units with their own status, notes, and history
- A **container registry** tracking flight cases, their tare weights, dimensions, and current contents
- A **load builder** (Pack-a-Load wizard) for assembling loads from available inventory at a location, with weight calculation and barcode scanning
- An **event scheduler** that automatically transitions fixture and container statuses when a linked event starts or ends

---

## Architecture

```
PostgreSQL
    ↕
FastAPI (Python 3.12+)          backend/
    ├── main.py                 App entry point, static file serving, lifespan scheduler
    ├── models.py               SQLAlchemy ORM table definitions
    ├── schemas.py              Pydantic v2 request/response schemas
    ├── database.py             Engine and session factory
    ├── config.py               Pydantic-settings configuration
    ├── scheduler.py            Background event status scheduler
    └── routers/
        ├── fixtures.py         Individual fixture units
        ├── fixture_models.py   Product model specs + preview images + file attachments
        ├── containers.py       Flight cases and packing units
        ├── locations.py        Warehouses, venues, sites
        ├── contacts.py         Suppliers, clients, venues
        ├── statuses.py         Configurable status labels
        ├── loads.py            Load manifests
        └── events.py           Events with date-triggered status changes

Vanilla HTML/CSS/JS             frontend/index.html     (single file, no build step)

File storage                    db/files/               Fixture and model file attachments
                                db/images/              Model preview images
```

---

## Data Model

### Core tables

| Table | Description |
|-------|-------------|
| `models` | Product specifications shared across fixture units. Stores name, category, subcategory, manufacturer, model number, weight, dimensions, power draw, and a preview image path. IDs start at 1001; ID 1001 is the reserved DUMMY model. |
| `fixtures` | Individual physical units. Each row is one fixture. Links to a model (for specs), a container (for location), and a status. Carries a short name and per-unit notes (serial numbers etc.). IDs start at 100001. |
| `containers` | Packing units (flight cases, dollies, etc.). Stores category, type, dimensions, tare weight, and current location. IDs 1–9999 are placeholder containers (one per location); IDs 10001+ are real containers. |
| `locations` | Physical sites. Each location has one placeholder container to hold unpackaged fixtures. |
| `contacts` | People and companies associated with locations. |
| `statuses` | Configurable status labels (e.g. "in storage", "packed", "on location"). |
| `events` | Named events with start and end dates. Linked to loads for automatic status transitions. |
| `loads` | A load manifest linking an origin location, destination location, optional event, selected containers, and selected fixtures. |
| `load_containers` | Join table: containers included in a load. |
| `load_fixtures` | Join table: fixtures included in a load, with an `included` flag for partial selections. |
| `load_log` | Audit log of load actions (activated, ended, etc.). |
| `status_change_log` | Per-entity status history with timestamps and load references. |
| `model_files` | File attachments (PDF, images) linked to models. |
| `fixture_files` | File attachments linked to individual fixtures. |

### Views

| View | Description |
|------|-------------|
| `v_fixtures_full` | Fixtures joined to model, status, container, and location. |
| `v_container_summary` | Containers with tare weight, fixture weight, total weight, volume, and fixture count. |
| `v_load_manifest` | Full load manifest with container and fixture details. |

---

## Prerequisites

### System requirements

- **Python 3.12+** — [python.org/downloads](https://www.python.org/downloads/)
- **PostgreSQL 14+** — [postgresql.org/download](https://www.postgresql.org/download/)
- **pip** — included with Python 3.12+

### Verify installations

```bash
python --version        # Python 3.12.x or higher
psql --version          # psql (PostgreSQL) 14.x or higher
pip --version
```

On Windows, `python` may be `py` and `psql` may need to be run from the PostgreSQL bin directory or added to PATH during installation.

---

## Building from Scratch

### 1. Create the project directory structure

```
sklad/
├── backend/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── schemas.py
│   ├── database.py
│   ├── config.py
│   ├── scheduler.py
│   └── routers/
│       ├── __init__.py
│       ├── fixtures.py
│       ├── fixture_models.py
│       ├── containers.py
│       ├── locations.py
│       ├── contacts.py
│       ├── statuses.py
│       ├── loads.py
│       └── events.py
├── frontend/
│   └── index.html
├── db/
│   ├── schema.sql
│   ├── files/          ← created automatically on first run
│   └── images/         ← created automatically on first run
├── requirements.txt
└── .env
```

### 2. Install Python dependencies

From the project root:

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install fastapi "uvicorn[standard]" SQLAlchemy psycopg2-binary pydantic-settings python-multipart
```

**Dependency reference:**

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | ≥ 0.111.0 | Web framework and REST API routing |
| `uvicorn[standard]` | ≥ 0.29.0 | ASGI server; `[standard]` adds performance extras |
| `SQLAlchemy` | ≥ 2.0.0 | ORM and database query layer |
| `psycopg2-binary` | ≥ 2.9.0 | PostgreSQL driver (binary build, no compiler needed) |
| `pydantic-settings` | ≥ 2.0.0 | `.env` file and environment variable configuration |
| `python-multipart` | ≥ 0.0.9 | Required by FastAPI for file uploads and form fields |

> `pydantic` v2 is installed automatically as a `fastapi` dependency.

### 3. Set up PostgreSQL

#### Create the database user (if needed)

```bash
psql -U postgres
```

```sql
CREATE USER sklad WITH PASSWORD 'yourpassword';
CREATE DATABASE warehouse_db OWNER sklad;
GRANT ALL PRIVILEGES ON DATABASE warehouse_db TO sklad;
\q
```

Or use the default `postgres` superuser for simplicity during development.

#### Create the database

```bash
createdb -U postgres warehouse_db
```

Or in psql:

```sql
CREATE DATABASE warehouse_db;
```

### 4. Apply the database schema

```bash
psql -U postgres -d warehouse_db -f db/schema.sql
```

This creates all tables, sequences, views, and inserts the required DUMMY model (ID 1001) and seed statuses.

### 5. Configure the connection

Create a `.env` file in the project root:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=warehouse_db
DB_USER=postgres
DB_PASS=yourpassword
```

All fields are optional — if omitted, the defaults above are used.

### 6. Create file storage directories

These are created automatically on first run, but you can create them manually:

```bash
mkdir -p db/files db/images
```

---

## Running the Server

Always run from the **project root directory** (the folder containing `backend/` and `frontend/`):

```bash
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

Then open your browser:

- **Application:** http://localhost:8000/app
- **API docs (Swagger UI):** http://localhost:8000/docs

The `--reload` flag restarts the server automatically when Python files change. Remove it for production use.

To bind to all network interfaces (accessible from other machines on the same network):

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

> **Do not run from inside the `backend/` directory.** The frontend is served as a static file from `frontend/index.html` relative to the working directory, and relative imports in the Python package will break.

---

## Daily Operations

### Starting the server

```bash
cd /path/to/sklad
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Stopping the server

`Ctrl+C` in the terminal running uvicorn.

### Backing up the database

```bash
pg_dump -U postgres warehouse_db > backup_$(date +%Y%m%d).sql
```

### Restoring from backup

```bash
psql -U postgres -d warehouse_db < backup_20250101.sql
```

### Applying a migration

When updating to a new version that includes migration files:

```bash
psql -U postgres -d warehouse_db -f db/migrate_<version>.sql
```

Always apply migrations in the order listed in the release notes. The current migration sequence from a fresh v0.8 install to v0.9:

```bash
psql -U postgres -d warehouse_db -f db/migrate_v3_part1_create.sql
psql -U postgres -d warehouse_db -f db/migrate_v3_part1b_reorder.sql
psql -U postgres -d warehouse_db -f db/migrate_v3_part1c_notes.sql
psql -U postgres -d warehouse_db -f db/migrate_v3_part1d_shortname.sql
psql -U postgres -d warehouse_db -f db/migrate_v3_part2_drop.sql
psql -U postgres -d warehouse_db -f db/migrate_fix_fixture_columns.sql
```

### Running on Windows

```bat
cd C:\path\to\sklad
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

If `python` is not recognised, try `py` instead. If `psql` is not in PATH, use the full path:

```bat
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres -d warehouse_db -f db\schema.sql
```

### Auto-starting on system boot (Linux — systemd)

Create `/etc/systemd/system/sklad.service`:

```ini
[Unit]
Description=SKLAD Warehouse Management
After=network.target postgresql.service

[Service]
WorkingDirectory=/path/to/sklad
ExecStart=/usr/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
Restart=always
User=youruser

[Install]
WantedBy=multi-user.target
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable sklad
sudo systemctl start sklad
```

---

## Frontend Tabs

### Fixtures

The primary working view. Split into a left tree pane and a right detail pane.

**Left pane — tree:**
- Hierarchical tree: Category → Subcategory → Short Name → Container → Fixture IDs
- Search field (Enter to apply) and filter popup (Location, Status, Manufacturer, Container type, Weight/Power sliders)
- Filter button shows a blue dot when any filter is active
- Click any 🔍 icon to open that level's detail in the right pane

**Right pane — detail:**
- Shows all fixtures, or filtered to a category/subcategory/model/container/individual fixture depending on what was clicked in the tree
- **Shift-click a column header** to group by that column; shift-click the same header to return to a flat ungrouped list. Default: grouped by Short Name
- Click a group header row to expand/collapse it
- **Shift-click any data cell** to edit it inline. Shift+drag to select multiple cells. Enter to commit, Escape to cancel
- Category and Name views show a model card at the top; Container view shows a container card
- Individual fixture view shows stacked model card → container card → fixture card

### Containers

Table of all containers with grouping, filtering, and inline editing.

- **Shift-click a column header** to group by that column; shift-click the same header to return to a flat list. Default: Category
- Filter popup: Location, Container type
- Columns: ID, Name, Category, Type, Location, W×D×H, Tare kg, Gross kg, Models, Units
- Click any row to expand it and see fixture contents with weight breakdown

### Models

Registry of all product models.

- **Shift-click a column header** to group by that column; shift-click the same header to return to a flat list. Default: Subcategory (two-level Category→Subcategory tree, all expanded)
- All fields are inline editable (shift-click)
- Expand a model row to see which containers hold fixtures of that model, then expand a container to see individual fixture IDs

### Locations, Contacts, Statuses

Standard CRUD tables. All fields are shift-click inline editable.

---

## Feature Reference

### Pack-a-Load Wizard

Accessed via the **▶ Pack a load** button on the Fixtures tab.

**Step 1:** Select origin location, destination location, and optional linked event.

**Step 2:** Select items to include.

- **Left pane (Available items):** Containers at the origin grouped by category, plus a LOOSE section for fixtures in placeholder containers
  - Colour coding on category headers: 🟢 all containers + all contents · 🟢/🟡 all containers + partial contents · 🟡/🟢 some containers + all contents · 🟡 some containers + partial contents
  - **Select all / Deselect all** buttons in the panel header
  - Barcode scanner input accepts container IDs (< 100000) or fixture IDs (≥ 100000)

- **Right pane (Load contents):** Selected containers and loose items
  - **+** button opens a combo input to add a fixture by short name
  - **✕** removes the container; qty +/− controls adjust unit counts

**Step 3:** Editable load summary with print export.

### Shift-Click Inline Editing

- **Shift-click** a data cell to activate it for editing
- **Shift+drag** across multiple cells to select a range; edit applies to all
- Enter commits and saves immediately; Escape cancels

### Shift-Click Column Grouping

- **Shift-click** a column header to group the table by that column
- **Shift-click the same header** to remove grouping and return to a flat list
- Active column is highlighted in blue with a ⊞ prefix
- Subcategory column produces a two-level Category→Subcategory tree

### Context-Aware Export

- **CSV:** All rows currently visible, respecting filters and grouping
- **Print:** Mirrors current grouping and expansion state exactly, including model cards with preview images

### Event Scheduler

When a load is linked to an event, the background scheduler (runs every 60 seconds) automatically sets all load fixtures and containers to "on location" at `start_date` and to "packed" at `end_date`. Missed transitions are caught up on server restart.

---

## API Reference

Interactive Swagger UI at **http://localhost:8000/docs**.

| Resource | Base path |
|----------|-----------|
| Fixtures | `/fixtures/` |
| Models | `/fixture-models/` |
| Containers | `/containers/` |
| Locations | `/locations/` |
| Contacts | `/contacts/` |
| Statuses | `/statuses/` |
| Events | `/events/` |
| Loads | `/loads/` |

All resources support `GET`, `POST`, `PUT /{id}`, `DELETE /{id}`. Most also support `PUT /{resource}/upsert/{id}` for create-or-update by ID, used by the CSV import system.

---

## File Storage

| Path | Contents |
|------|----------|
| `db/files/` | Fixture and model file attachments. Stored with UUID-based filenames; original names preserved in the database. |
| `db/images/` | Model preview images. Files can be placed here manually and matched to models via `POST /fixture-models/preview/auto-assign-all`. |

Both directories are created automatically on first run. Maximum upload size: 20 MB. Allowed types: PDF, PNG, JPEG, WebP.

---

## Environment Variables

All variables are optional. Defaults are used if no `.env` file is present.

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_HOST` | `localhost` | PostgreSQL host |
| `DB_PORT` | `5432` | PostgreSQL port |
| `DB_NAME` | `warehouse_db` | Database name |
| `DB_USER` | `postgres` | Database user |
| `DB_PASS` | `postgres` | Database password |

Set in a `.env` file in the project root, or as system environment variables. The `.env` file is read automatically on startup.
