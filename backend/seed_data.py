"""Populate the database with realistic sample data for demoing the UI."""

from database import get_db, init_db

LOCATIONS = [
    ("HQ - Data Center 1", "New York", "Building A", "B1", "DC-101", "Primary DC, raised floor"),
    ("HQ - Network Closet 3F", "New York", "Building A", "3", "NC-304", ""),
    ("Chicago Branch", "Chicago", "Riverside Tower", "12", "IT-1201", ""),
    ("Remote - AWS us-east-1", "Cloud", "", "", "", "Virtual location for cloud assets"),
]

DEVICES = [
    ("core-sw-01", "switch", "Cisco", "Catalyst 9300", "SN-CS9300-001", "AA:BB:CC:00:01:01",
     "active", "IOS-XE 17.9", 1, "2022-01-15", "2027-01-15", "Core switch, stacked with core-sw-02",
     [("10.0.0.1", "management", "255.255.255.0", 1)]),
    ("core-sw-02", "switch", "Cisco", "Catalyst 9300", "SN-CS9300-002", "AA:BB:CC:00:01:02",
     "active", "IOS-XE 17.9", 1, "2022-01-15", "2027-01-15", "Stack member",
     [("10.0.0.2", "management", "255.255.255.0", 1)]),
    ("edge-fw-01", "firewall", "Palo Alto", "PA-3220", "SN-PA3220-101", "AA:BB:CC:00:02:01",
     "active", "PAN-OS 11.1", 1, "2023-03-01", "2026-03-01", "Perimeter firewall",
     [("10.0.0.254", "management", "255.255.255.0", None), ("203.0.113.10", "primary", None, None)]),
    ("dc1-rtr-01", "router", "Juniper", "MX204", "SN-MX204-201", "AA:BB:CC:00:03:01",
     "active", "Junos 22.4", 1, "2021-11-20", "2026-11-20", "WAN edge router", []),
    ("ap-3f-hallway", "access_point", "Ubiquiti", "U6-Pro", "SN-U6P-501", "AA:BB:CC:00:04:01",
     "active", "6.6.55", 2, "2023-06-10", "2025-06-10", "", [("10.0.3.15", "management", None, 30)]),
    ("ap-3f-conf-room", "access_point", "Ubiquiti", "U6-Pro", "SN-U6P-502", "AA:BB:CC:00:04:02",
     "maintenance", "6.6.55", 2, "2023-06-10", "2025-06-10", "Firmware update pending",
     [("10.0.3.16", "management", None, 30)]),
    ("app-srv-01", "server", "Dell", "PowerEdge R650", "SN-R650-301", "AA:BB:CC:00:05:01",
     "active", "Ubuntu 22.04 LTS", 1, "2022-08-01", "2027-08-01", "Primary application server",
     [("10.0.1.10", "primary", "255.255.255.0", None)]),
    ("db-srv-01", "server", "Dell", "PowerEdge R750", "SN-R750-302", "AA:BB:CC:00:05:02",
     "active", "Ubuntu 22.04 LTS", 1, "2022-08-01", "2027-08-01", "PostgreSQL primary",
     [("10.0.1.11", "primary", "255.255.255.0", None)]),
    ("branch-sw-01", "switch", "Cisco", "Catalyst 9200", "SN-CS9200-401", "AA:BB:CC:00:06:01",
     "active", "IOS-XE 17.6", 3, "2022-05-05", "2027-05-05", "", [("172.16.10.1", "management", "255.255.255.0", None)]),
    ("branch-fw-01", "firewall", "Fortinet", "FortiGate 100F", "SN-FG100F-402", "AA:BB:CC:00:06:02",
     "offline", "FortiOS 7.2", 3, "2022-05-05", "2027-05-05", "Offline pending replacement", []),
    ("cloud-lb-01", "load_balancer", "AWS", "Application Load Balancer", "N/A", None,
     "active", "n/a", 4, None, None, "Public-facing ALB", [("198.51.100.20", "primary", None, None)]),
    ("legacy-print-2f", "printer", "HP", "LaserJet Enterprise M610", "SN-HPLJ-901", "AA:BB:CC:00:07:01",
     "decommissioned", "", 2, "2018-02-01", "2021-02-01", "Awaiting disposal", []),
]


def seed():
    init_db()
    with get_db() as conn:
        conn.execute("DELETE FROM ip_addresses")
        conn.execute("DELETE FROM devices")
        conn.execute("DELETE FROM locations")

        loc_ids = []
        for name, site, building, floor, room, notes in LOCATIONS:
            cur = conn.execute(
                "INSERT INTO locations (name, site, building, floor, room, notes) VALUES (?,?,?,?,?,?)",
                (name, site, building, floor, room, notes),
            )
            loc_ids.append(cur.lastrowid)

        for (hostname, dtype, mfr, model, serial, mac, status, osv, loc_idx,
             purchase, warranty, notes, ips) in DEVICES:
            location_id = loc_ids[loc_idx - 1] if loc_idx else None
            cur = conn.execute(
                """INSERT INTO devices
                   (hostname, device_type, manufacturer, model, serial_number, mac_address,
                    status, os_version, location_id, purchase_date, warranty_expiry, notes)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (hostname, dtype, mfr, model, serial, mac, status, osv, location_id,
                 purchase, warranty, notes),
            )
            device_id = cur.lastrowid
            for ip_address, ip_type, mask, vlan in ips:
                conn.execute(
                    """INSERT INTO ip_addresses (device_id, ip_address, ip_type, subnet_mask, vlan_id)
                       VALUES (?,?,?,?,?)""",
                    (device_id, ip_address, ip_type, mask, vlan),
                )

    print(f"Seeded {len(LOCATIONS)} locations and {len(DEVICES)} devices.")


if __name__ == "__main__":
    seed()
