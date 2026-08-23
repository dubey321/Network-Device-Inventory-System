-- ============================================================
-- Network Device Inventory System — MySQL schema
-- Run with: mysql -u youruser -p inventory < schema_mysql.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS locations (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(150) NOT NULL UNIQUE,
    site        VARCHAR(150),
    building    VARCHAR(100),
    floor       VARCHAR(50),
    room        VARCHAR(50),
    notes       TEXT,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS devices (
    id              INT AUTO_INCREMENT PRIMARY KEY,
    hostname        VARCHAR(150) NOT NULL UNIQUE,
    device_type     ENUM('router','switch','firewall','access_point','server',
                         'load_balancer','printer','ups','other') NOT NULL,
    manufacturer    VARCHAR(100),
    model           VARCHAR(100),
    serial_number   VARCHAR(150) UNIQUE,
    mac_address     VARCHAR(17),
    status          ENUM('active','maintenance','offline','decommissioned')
                        NOT NULL DEFAULT 'active',
    os_version      VARCHAR(100),
    location_id     INT,
    purchase_date   DATE,
    warranty_expiry DATE,
    notes           TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (location_id) REFERENCES locations(id) ON DELETE SET NULL
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS ip_addresses (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    device_id   INT NOT NULL,
    ip_address  VARCHAR(45) NOT NULL UNIQUE,
    ip_type     ENUM('management','primary','secondary','vlan')
                    NOT NULL DEFAULT 'management',
    subnet_mask VARCHAR(15),
    vlan_id     INT,
    FOREIGN KEY (device_id) REFERENCES devices(id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE INDEX idx_devices_status   ON devices(status);
CREATE INDEX idx_devices_type     ON devices(device_type);
CREATE INDEX idx_devices_location ON devices(location_id);
CREATE INDEX idx_ip_device        ON ip_addresses(device_id);
