-- ============================================================
-- Network Device Inventory System — PostgreSQL schema
-- Run with: psql -U youruser -d inventory -f schema_postgresql.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS locations (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(150) NOT NULL UNIQUE,
    site        VARCHAR(150),
    building    VARCHAR(100),
    floor       VARCHAR(50),
    room        VARCHAR(50),
    notes       TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TYPE device_type_enum AS ENUM
    ('router','switch','firewall','access_point','server','load_balancer','printer','ups','other');
CREATE TYPE device_status_enum AS ENUM
    ('active','maintenance','offline','decommissioned');
CREATE TYPE ip_type_enum AS ENUM
    ('management','primary','secondary','vlan');

CREATE TABLE IF NOT EXISTS devices (
    id              SERIAL PRIMARY KEY,
    hostname        VARCHAR(150) NOT NULL UNIQUE,
    device_type     device_type_enum NOT NULL,
    manufacturer    VARCHAR(100),
    model           VARCHAR(100),
    serial_number   VARCHAR(150) UNIQUE,
    mac_address     VARCHAR(17),
    status          device_status_enum NOT NULL DEFAULT 'active',
    os_version      VARCHAR(100),
    location_id     INTEGER REFERENCES locations(id) ON DELETE SET NULL,
    purchase_date   DATE,
    warranty_expiry DATE,
    notes           TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ip_addresses (
    id          SERIAL PRIMARY KEY,
    device_id   INTEGER NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    ip_address  INET NOT NULL UNIQUE,
    ip_type     ip_type_enum NOT NULL DEFAULT 'management',
    subnet_mask VARCHAR(15),
    vlan_id     INTEGER
);

CREATE INDEX IF NOT EXISTS idx_devices_status   ON devices(status);
CREATE INDEX IF NOT EXISTS idx_devices_type     ON devices(device_type);
CREATE INDEX IF NOT EXISTS idx_devices_location ON devices(location_id);
CREATE INDEX IF NOT EXISTS idx_ip_device        ON ip_addresses(device_id);

-- keep updated_at current on every UPDATE
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_devices_updated_at
BEFORE UPDATE ON devices
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
