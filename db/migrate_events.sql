-- ============================================================
-- Migration: add events table + event_id to loads
-- Run this against an existing warehouse_db
-- Safe to run multiple times (uses IF NOT EXISTS)
-- ============================================================

-- Events table
CREATE TABLE IF NOT EXISTS events (
    event_id    SERIAL PRIMARY KEY,
    short_name  VARCHAR(128) NOT NULL,
    event_type  VARCHAR(64),
    location_id INT REFERENCES locations(location_id) ON DELETE SET NULL,
    contact_id  INT REFERENCES contacts(contact_id)   ON DELETE SET NULL,
    start_date  TIMESTAMPTZ,
    end_date    TIMESTAMPTZ,
    description TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_location ON events(location_id);
CREATE INDEX IF NOT EXISTS idx_events_dates    ON events(start_date, end_date);

-- Add event_id to loads if not present
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='loads' AND column_name='event_id'
    ) THEN
        ALTER TABLE loads ADD COLUMN event_id INT REFERENCES events(event_id) ON DELETE SET NULL;
    END IF;
END $$;

-- Add event_activated flag to loads (prevents double-firing scheduler)
DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='loads' AND column_name='event_activated'
    ) THEN
        ALTER TABLE loads ADD COLUMN event_activated BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
END $$;

DO $$ BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='loads' AND column_name='event_ended'
    ) THEN
        ALTER TABLE loads ADD COLUMN event_ended BOOLEAN NOT NULL DEFAULT FALSE;
    END IF;
END $$;

SELECT 'Migration complete.' AS result;
