-- ============================================================
-- Network Device Inventory System — SQLite schema
-- (PostgreSQL and MySQL equivalents live in schema_postgresql.sql
--  and schema_mysql.sql — the shape is identical, only column
--  types / autoincrement syntax differ)
-- ============================================================

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS locations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL UNIQUE,     -- e.g. "HQ - Data Center 1"
    site        TEXT,                     -- campus / city
    building    TEXT,
    floor       TEXT,
    room        TEXT,
    notes       TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS devices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    hostname        TEXT NOT NULL UNIQUE,
    device_type     TEXT NOT NULL CHECK (device_type IN
                        ('router','switch','firewall','access_point',
                         'server','load_balancer','printer','ups','other')),
    manufacturer    TEXT,
    model           TEXT,
    serial_number   TEXT UNIQUE,
    mac_address     TEXT,
    status          TEXT NOT NULL DEFAULT 'active' CHECK (status IN
                        ('active','maintenance','offline','decommissioned')),
    os_version      TEXT,
    location_id     INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    purchase_date   TEXT,
    warranty_expiry TEXT,
    notes           TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- A device can legitimately hold more than one IP address
-- (management IP, VLAN interfaces, secondary NICs, etc.)
CREATE TABLE IF NOT EXISTS ip_addresses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id   INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    ip_address  TEXT NOT NULL,
    ip_type     TEXT NOT NULL DEFAULT 'management' CHECK (ip_type IN
                        ('management','primary','secondary','vlan')),
    subnet_mask TEXT,
    vlan_id     INTEGER,
    UNIQUE(ip_address)
);

CREATE INDEX IF NOT EXISTS idx_devices_status   ON devices(status);
CREATE INDEX IF NOT EXISTS idx_devices_type     ON devices(device_type);
CREATE INDEX IF NOT EXISTS idx_devices_location ON devices(location_id);
CREATE INDEX IF NOT EXISTS idx_ip_device        ON ip_addresses(device_id);
