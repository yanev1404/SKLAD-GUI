-- ============================================================
-- warehouse_db schema
-- PostgreSQL 15+
-- ============================================================

-- Drop in dependency order if rebuilding
DROP TABLE IF EXISTS status_change_log  CASCADE;
DROP TABLE IF EXISTS load_log           CASCADE;
DROP TABLE IF EXISTS load_fixtures      CASCADE;
DROP TABLE IF EXISTS load_containers    CASCADE;
DROP TABLE IF EXISTS loads              CASCADE;
DROP TABLE IF EXISTS fixtures           CASCADE;
DROP TABLE IF EXISTS containers         CASCADE;
DROP TABLE IF EXISTS locations          CASCADE;
DROP TABLE IF EXISTS contacts           CASCADE;
DROP TABLE IF EXISTS statuses           CASCADE;

-- ============================================================
-- STATUSES  (user-managed, free text)
-- ============================================================
CREATE TABLE statuses (
    status_id   SERIAL PRIMARY KEY,
    name        VARCHAR(64)  NOT NULL UNIQUE,
    description TEXT,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- Seed default statuses
INSERT INTO statuses (name, description) VALUES
    ('in storage',   'Item is at its home location, not assigned to any load'),
    ('packed',       'Item is packed into a container assigned to an active load'),
    ('in transit',   'Load has been dispatched, items are on the move'),
    ('on location',  'Item is deployed at an event or external location'),
    ('in repair',    'Item is with a service provider or flagged for maintenance'),
    ('retired',      'Item is written off and no longer in active inventory');

-- ============================================================
-- CONTACTS
-- ============================================================
CREATE TABLE contacts (
    contact_id  SERIAL PRIMARY KEY,
    company     VARCHAR(128),
    first_name  VARCHAR(64),
    last_name   VARCHAR(64),
    phone       VARCHAR(32),
    email       VARCHAR(128),
    note        TEXT
);

-- ============================================================
-- LOCATIONS
-- ============================================================
CREATE TABLE locations (
    location_id             SERIAL PRIMARY KEY,
    name                    VARCHAR(128) NOT NULL,
    type                    VARCHAR(64),          -- e.g. warehouse, venue, depot, workshop
    short_name              VARCHAR(32)  NOT NULL UNIQUE,
    address                 VARCHAR(255),
    city                    VARCHAR(64),
    contact_id              INT REFERENCES contacts(contact_id) ON DELETE SET NULL,
    placeholder_container_id INT,                 -- set after containers table exists (FK added below)
    note                    TEXT
);

-- ============================================================
-- CONTAINERS
-- ============================================================
CREATE TABLE containers (
    container_id  SERIAL PRIMARY KEY,
    category      VARCHAR(64),
    container_type VARCHAR(64),
    short_name    VARCHAR(64)  NOT NULL,
    location_id   INT REFERENCES locations(location_id) ON DELETE SET NULL,
    weight_kg     NUMERIC(8,2),
    width_cm      NUMERIC(8,2),
    depth_cm      NUMERIC(8,2),
    height_cm     NUMERIC(8,2),
    status_id     INT REFERENCES statuses(status_id) ON DELETE SET NULL,
    note          TEXT
);

-- Now that containers table exists, add the FK on locations
ALTER TABLE locations
    ADD CONSTRAINT fk_placeholder_container
    FOREIGN KEY (placeholder_container_id)
    REFERENCES containers(container_id)
    ON DELETE SET NULL;

-- ============================================================
-- FIXTURES
-- ============================================================
CREATE TABLE fixtures (
    fixture_id    SERIAL PRIMARY KEY,
    category      VARCHAR(64),
    subcategory   VARCHAR(64),
    short_name    VARCHAR(128) NOT NULL,
    quantity      INT          NOT NULL DEFAULT 1,
    manufacturer  VARCHAR(128),
    model         VARCHAR(128),
    weight_kg     NUMERIC(8,2),
    power_w       NUMERIC(8,2),
    container_id  INT REFERENCES containers(container_id) ON DELETE SET NULL,
    status_id     INT REFERENCES statuses(status_id) ON DELETE SET NULL,
    note          TEXT
);

-- ============================================================
-- LOADS
-- ============================================================
CREATE TABLE loads (
    load_id                 SERIAL PRIMARY KEY,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    origin_location_id      INT REFERENCES locations(location_id) ON DELETE SET NULL,
    destination_location_id INT REFERENCES locations(location_id) ON DELETE SET NULL,
    status                  VARCHAR(32) NOT NULL DEFAULT 'completed'
                                CHECK (status IN ('completed', 'storno')),
    note                    TEXT
);

-- ============================================================
-- LOAD CONTAINERS  (which containers are on a load)
-- ============================================================
CREATE TABLE load_containers (
    id            SERIAL PRIMARY KEY,
    load_id       INT NOT NULL REFERENCES loads(load_id) ON DELETE CASCADE,
    container_id  INT NOT NULL REFERENCES containers(container_id) ON DELETE CASCADE,
    UNIQUE (load_id, container_id)
);

-- ============================================================
-- LOAD FIXTURES  (per-fixture inclusion flag)
-- ============================================================
CREATE TABLE load_fixtures (
    id          SERIAL PRIMARY KEY,
    load_id     INT  NOT NULL REFERENCES loads(load_id) ON DELETE CASCADE,
    fixture_id  INT  NOT NULL REFERENCES fixtures(fixture_id) ON DELETE CASCADE,
    included    BOOLEAN NOT NULL DEFAULT TRUE,
    -- FALSE = deselected; item stays at origin in placeholder container
    UNIQUE (load_id, fixture_id)
);

-- ============================================================
-- LOAD LOG  (one row per lifecycle event on a load)
-- ============================================================
CREATE TABLE load_log (
    log_id     SERIAL PRIMARY KEY,
    load_id    INT NOT NULL REFERENCES loads(load_id) ON DELETE CASCADE,
    timestamp  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    action     VARCHAR(64) NOT NULL,
    -- 'created' | 'completed' | 'storno_initiated' | 'storno_completed'
    note       TEXT
);

-- ============================================================
-- STATUS CHANGE LOG  (full audit trail for every status change)
-- ============================================================
CREATE TABLE status_change_log (
    log_id       SERIAL PRIMARY KEY,
    entity_type  VARCHAR(16) NOT NULL CHECK (entity_type IN ('fixture', 'container')),
    entity_id    INT         NOT NULL,
    old_status_id INT REFERENCES statuses(status_id) ON DELETE SET NULL,
    new_status_id INT REFERENCES statuses(status_id) ON DELETE SET NULL,
    load_id      INT REFERENCES loads(load_id) ON DELETE SET NULL,  -- NULL = manual change
    timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    note         TEXT
);

-- ============================================================
-- INDEXES
-- ============================================================
CREATE INDEX idx_fixtures_container    ON fixtures(container_id);
CREATE INDEX idx_fixtures_status       ON fixtures(status_id);
CREATE INDEX idx_containers_location   ON containers(location_id);
CREATE INDEX idx_containers_status     ON containers(status_id);
CREATE INDEX idx_load_containers_load  ON load_containers(load_id);
CREATE INDEX idx_load_fixtures_load    ON load_fixtures(load_id);
CREATE INDEX idx_status_log_entity     ON status_change_log(entity_type, entity_id);
CREATE INDEX idx_status_log_load       ON status_change_log(load_id);

-- ============================================================
-- VIEWS
-- ============================================================

-- All fixtures with their container and location
CREATE OR REPLACE VIEW v_fixtures_full AS
SELECT
    f.fixture_id,
    f.short_name,
    f.category,
    f.subcategory,
    f.quantity,
    f.manufacturer,
    f.model,
    f.weight_kg,
    f.power_w,
    s.name        AS status,
    c.short_name  AS container,
    c.container_id,
    l.short_name  AS location,
    l.location_id,
    f.note
FROM fixtures f
LEFT JOIN statuses   s ON s.status_id   = f.status_id
LEFT JOIN containers c ON c.container_id = f.container_id
LEFT JOIN locations  l ON l.location_id  = c.location_id;

-- Container summary with weight/volume and fixture count
CREATE OR REPLACE VIEW v_container_summary AS
SELECT
    c.container_id,
    c.short_name,
    c.category,
    c.container_type,
    l.short_name                            AS location,
    l.location_id,
    s.name                                  AS status,
    c.weight_kg                             AS tare_weight_kg,
    COALESCE(SUM(f.weight_kg * f.quantity), 0)           AS fixtures_weight_kg,
    c.weight_kg + COALESCE(SUM(f.weight_kg * f.quantity), 0) AS total_weight_kg,
    (c.width_cm * c.depth_cm * c.height_cm) / 1000000.0 AS volume_m3,
    COUNT(f.fixture_id)                     AS fixture_types_count,
    COALESCE(SUM(f.quantity), 0)            AS fixture_units_count,
    c.width_cm,
    c.depth_cm,
    c.height_cm,
    c.note
FROM containers c
LEFT JOIN locations  l ON l.location_id  = c.location_id
LEFT JOIN statuses   s ON s.status_id    = c.status_id
LEFT JOIN fixtures   f ON f.container_id = c.container_id
GROUP BY c.container_id, l.location_id, l.short_name, s.name;

-- Load manifest report (all containers + fixtures for a given load)
CREATE OR REPLACE VIEW v_load_manifest AS
SELECT
    ld.load_id,
    ld.created_at,
    ld.status                               AS load_status,
    ol.short_name                           AS origin,
    dl.short_name                           AS destination,
    c.container_id,
    c.short_name                            AS container_name,
    c.weight_kg                             AS container_tare_kg,
    (c.width_cm * c.depth_cm * c.height_cm) / 1000000.0 AS container_volume_m3,
    f.fixture_id,
    f.short_name                            AS fixture_name,
    f.quantity,
    f.weight_kg                             AS fixture_weight_kg,
    lf.included
FROM loads ld
JOIN locations  ol  ON ol.location_id  = ld.origin_location_id
JOIN locations  dl  ON dl.location_id  = ld.destination_location_id
JOIN load_containers lc ON lc.load_id  = ld.load_id
JOIN containers c       ON c.container_id = lc.container_id
LEFT JOIN load_fixtures lf ON lf.load_id = ld.load_id AND lf.fixture_id IN (
    SELECT fixture_id FROM fixtures WHERE container_id = c.container_id
)
LEFT JOIN fixtures f ON f.fixture_id = lf.fixture_id;

-- ============================================================
-- SEED: Warehouse location + its placeholder container
-- ============================================================
-- Insert default warehouse location
INSERT INTO locations (name, type, short_name, address, city, note)
VALUES ('Main Warehouse', 'warehouse', 'WH-MAIN', NULL, NULL, 'Default warehouse location');

-- Insert its placeholder container
INSERT INTO containers (category, container_type, short_name, location_id, note)
VALUES ('placeholder', 'placeholder', 'WH-MAIN',
        (SELECT location_id FROM locations WHERE short_name = 'WH-MAIN'),
        'Auto-generated placeholder for WH-MAIN');

-- Link placeholder back to location
UPDATE locations
SET placeholder_container_id = (
    SELECT container_id FROM containers WHERE short_name = 'WH-MAIN' AND container_type = 'placeholder'
)
WHERE short_name = 'WH-MAIN';
