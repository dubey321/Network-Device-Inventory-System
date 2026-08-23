"""
Network Device Inventory System — Flask REST API

Endpoints
---------
Devices
  GET    /api/devices                 list devices (filters: type, status, location_id, q)
  GET    /api/devices/<id>            single device incl. location + ip addresses
  POST   /api/devices                 create device
  PUT    /api/devices/<id>            update device
  DELETE /api/devices/<id>            delete device

IP addresses (belong to a device)
  POST   /api/devices/<id>/ips        add an IP to a device
  DELETE /api/ips/<ip_id>             remove an IP

Locations
  GET    /api/locations               list locations
  POST   /api/locations               create location
  PUT    /api/locations/<id>          update location
  DELETE /api/locations/<id>          delete location

Dashboard
  GET    /api/stats                   counts by status / type / location

Health
  GET    /api/health
"""

import re
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
import os

from database import get_db, init_db, row_to_dict, rows_to_list

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

app = Flask(__name__, static_folder=None)

VALID_DEVICE_TYPES = {"router", "switch", "firewall", "access_point", "server",
                       "load_balancer", "printer", "ups", "other"}
VALID_STATUSES = {"active", "maintenance", "offline", "decommissioned"}
VALID_IP_TYPES = {"management", "primary", "secondary", "vlan"}

IPV4_RE = re.compile(
    r"^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$"
)
MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")


# ---------------------------------------------------------------- helpers --

def bad_request(message, code=400):
    return jsonify({"error": message}), code


def not_found(message="Resource not found"):
    return jsonify({"error": message}), 404


@app.after_request
def add_cors_headers(response):
    """Manual CORS so the frontend (served from any origin/port) can call the API."""
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


@app.route("/api/<path:_any>", methods=["OPTIONS"])
def cors_preflight(_any):
    return "", 204


def fetch_device_full(conn, device_id):
    device = conn.execute(
        """SELECT d.*, l.name AS location_name, l.site AS location_site,
                  l.building AS location_building, l.room AS location_room
           FROM devices d
           LEFT JOIN locations l ON l.id = d.location_id
           WHERE d.id = ?""",
        (device_id,),
    ).fetchone()
    if device is None:
        return None
    device = row_to_dict(device)
    ips = conn.execute(
        "SELECT * FROM ip_addresses WHERE device_id = ? ORDER BY id", (device_id,)
    ).fetchall()
    device["ip_addresses"] = rows_to_list(ips)
    return device


# ---------------------------------------------------------------- devices --

@app.route("/api/devices", methods=["GET"])
def list_devices():
    device_type = request.args.get("type")
    status = request.args.get("status")
    location_id = request.args.get("location_id")
    q = request.args.get("q", "").strip()

    query = """
        SELECT d.*, l.name AS location_name
        FROM devices d
        LEFT JOIN locations l ON l.id = d.location_id
        WHERE 1=1
    """
    params = []

    if device_type:
        if device_type not in VALID_DEVICE_TYPES:
            return bad_request(f"Invalid type filter '{device_type}'")
        query += " AND d.device_type = ?"
        params.append(device_type)

    if status:
        if status not in VALID_STATUSES:
            return bad_request(f"Invalid status filter '{status}'")
        query += " AND d.status = ?"
        params.append(status)

    if location_id:
        query += " AND d.location_id = ?"
        params.append(location_id)

    if q:
        query += """ AND (d.hostname LIKE ? OR d.manufacturer LIKE ?
                           OR d.model LIKE ? OR d.serial_number LIKE ?
                           OR d.mac_address LIKE ?
                           OR EXISTS (SELECT 1 FROM ip_addresses i
                                      WHERE i.device_id = d.id AND i.ip_address LIKE ?))"""
        like = f"%{q}%"
        params += [like, like, like, like, like, like]

    query += " ORDER BY d.hostname"

    with get_db() as conn:
        rows = conn.execute(query, params).fetchall()
        devices = rows_to_list(rows)
        # attach ip addresses for each device in one extra query (avoid N+1 fan-out)
        ids = [d["id"] for d in devices]
        ip_map = {}
        if ids:
            placeholders = ",".join("?" * len(ids))
            ip_rows = conn.execute(
                f"SELECT * FROM ip_addresses WHERE device_id IN ({placeholders})", ids
            ).fetchall()
            for ip in rows_to_list(ip_rows):
                ip_map.setdefault(ip["device_id"], []).append(ip)
        for d in devices:
            d["ip_addresses"] = ip_map.get(d["id"], [])

    return jsonify(devices)


@app.route("/api/devices/<int:device_id>", methods=["GET"])
def get_device(device_id):
    with get_db() as conn:
        device = fetch_device_full(conn, device_id)
    if device is None:
        return not_found("Device not found")
    return jsonify(device)


def validate_device_payload(data, partial=False):
    errors = []

    if not partial or "hostname" in data:
        if not data.get("hostname", "").strip():
            errors.append("hostname is required")

    if not partial or "device_type" in data:
        if data.get("device_type") not in VALID_DEVICE_TYPES:
            errors.append(f"device_type must be one of {sorted(VALID_DEVICE_TYPES)}")

    if "status" in data and data["status"] not in VALID_STATUSES:
        errors.append(f"status must be one of {sorted(VALID_STATUSES)}")

    if data.get("mac_address"):
        if not MAC_RE.match(data["mac_address"]):
            errors.append("mac_address must look like AA:BB:CC:DD:EE:FF")

    return errors


@app.route("/api/devices", methods=["POST"])
def create_device():
    data = request.get_json(silent=True) or {}
    errors = validate_device_payload(data)
    if errors:
        return bad_request("; ".join(errors))

    fields = ("hostname", "device_type", "manufacturer", "model", "serial_number",
              "mac_address", "status", "os_version", "location_id",
              "purchase_date", "warranty_expiry", "notes")
    values = {f: data.get(f) for f in fields}
    values["status"] = values["status"] or "active"

    try:
        with get_db() as conn:
            cur = conn.execute(
                f"""INSERT INTO devices ({",".join(fields)})
                    VALUES ({",".join("?" * len(fields))})""",
                [values[f] for f in fields],
            )
            device_id = cur.lastrowid

            for ip in data.get("ip_addresses", []):
                _insert_ip(conn, device_id, ip)

            device = fetch_device_full(conn, device_id)
    except sqlite3.IntegrityError as e:
        return bad_request(f"Could not create device: {e}")

    return jsonify(device), 201


@app.route("/api/devices/<int:device_id>", methods=["PUT"])
def update_device(device_id):
    data = request.get_json(silent=True) or {}
    errors = validate_device_payload(data, partial=True)
    if errors:
        return bad_request("; ".join(errors))

    fields = ("hostname", "device_type", "manufacturer", "model", "serial_number",
              "mac_address", "status", "os_version", "location_id",
              "purchase_date", "warranty_expiry", "notes")
    updates = {f: data[f] for f in fields if f in data}
    if not updates:
        return bad_request("No updatable fields provided")

    set_clause = ", ".join(f"{f} = ?" for f in updates)
    try:
        with get_db() as conn:
            existing = conn.execute("SELECT id FROM devices WHERE id = ?", (device_id,)).fetchone()
            if existing is None:
                return not_found("Device not found")
            conn.execute(
                f"UPDATE devices SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
                [*updates.values(), device_id],
            )
            device = fetch_device_full(conn, device_id)
    except sqlite3.IntegrityError as e:
        return bad_request(f"Could not update device: {e}")

    return jsonify(device)


@app.route("/api/devices/<int:device_id>", methods=["DELETE"])
def delete_device(device_id):
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM devices WHERE id = ?", (device_id,)).fetchone()
        if existing is None:
            return not_found("Device not found")
        conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))
    return jsonify({"message": "Device deleted"}), 200


# ------------------------------------------------------------- ip addresses --

def _insert_ip(conn, device_id, ip_payload):
    ip_address = (ip_payload.get("ip_address") or "").strip()
    if not IPV4_RE.match(ip_address):
        raise ValueError(f"'{ip_address}' is not a valid IPv4 address")
    ip_type = ip_payload.get("ip_type", "management")
    if ip_type not in VALID_IP_TYPES:
        raise ValueError(f"ip_type must be one of {sorted(VALID_IP_TYPES)}")
    conn.execute(
        """INSERT INTO ip_addresses (device_id, ip_address, ip_type, subnet_mask, vlan_id)
           VALUES (?, ?, ?, ?, ?)""",
        (device_id, ip_address, ip_type, ip_payload.get("subnet_mask"), ip_payload.get("vlan_id")),
    )


@app.route("/api/devices/<int:device_id>/ips", methods=["POST"])
def add_ip(device_id):
    data = request.get_json(silent=True) or {}
    try:
        with get_db() as conn:
            device = conn.execute("SELECT id FROM devices WHERE id = ?", (device_id,)).fetchone()
            if device is None:
                return not_found("Device not found")
            _insert_ip(conn, device_id, data)
            full = fetch_device_full(conn, device_id)
    except (ValueError, sqlite3.IntegrityError) as e:
        return bad_request(str(e))
    return jsonify(full), 201


@app.route("/api/ips/<int:ip_id>", methods=["DELETE"])
def delete_ip(ip_id):
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM ip_addresses WHERE id = ?", (ip_id,)).fetchone()
        if existing is None:
            return not_found("IP address not found")
        conn.execute("DELETE FROM ip_addresses WHERE id = ?", (ip_id,))
    return jsonify({"message": "IP address removed"}), 200


# ---------------------------------------------------------------- locations --

@app.route("/api/locations", methods=["GET"])
def list_locations():
    with get_db() as conn:
        rows = conn.execute(
            """SELECT l.*,
                      (SELECT COUNT(*) FROM devices d WHERE d.location_id = l.id) AS device_count
               FROM locations l ORDER BY l.name"""
        ).fetchall()
    return jsonify(rows_to_list(rows))


@app.route("/api/locations", methods=["POST"])
def create_location():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return bad_request("name is required")
    fields = ("name", "site", "building", "floor", "room", "notes")
    values = {f: data.get(f) for f in fields}
    try:
        with get_db() as conn:
            cur = conn.execute(
                f"""INSERT INTO locations ({",".join(fields)})
                    VALUES ({",".join("?" * len(fields))})""",
                [values[f] for f in fields],
            )
            row = conn.execute("SELECT * FROM locations WHERE id = ?", (cur.lastrowid,)).fetchone()
    except sqlite3.IntegrityError as e:
        return bad_request(f"Could not create location: {e}")
    return jsonify(row_to_dict(row)), 201


@app.route("/api/locations/<int:location_id>", methods=["PUT"])
def update_location(location_id):
    data = request.get_json(silent=True) or {}
    fields = ("name", "site", "building", "floor", "room", "notes")
    updates = {f: data[f] for f in fields if f in data}
    if not updates:
        return bad_request("No updatable fields provided")
    set_clause = ", ".join(f"{f} = ?" for f in updates)
    try:
        with get_db() as conn:
            existing = conn.execute("SELECT id FROM locations WHERE id = ?", (location_id,)).fetchone()
            if existing is None:
                return not_found("Location not found")
            conn.execute(f"UPDATE locations SET {set_clause} WHERE id = ?",
                         [*updates.values(), location_id])
            row = conn.execute("SELECT * FROM locations WHERE id = ?", (location_id,)).fetchone()
    except sqlite3.IntegrityError as e:
        return bad_request(f"Could not update location: {e}")
    return jsonify(row_to_dict(row))


@app.route("/api/locations/<int:location_id>", methods=["DELETE"])
def delete_location(location_id):
    with get_db() as conn:
        existing = conn.execute("SELECT id FROM locations WHERE id = ?", (location_id,)).fetchone()
        if existing is None:
            return not_found("Location not found")
        conn.execute("DELETE FROM locations WHERE id = ?", (location_id,))
    return jsonify({"message": "Location deleted"}), 200


# -------------------------------------------------------------------- stats --

@app.route("/api/stats", methods=["GET"])
def stats():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) AS c FROM devices").fetchone()["c"]
        by_status = rows_to_list(conn.execute(
            "SELECT status, COUNT(*) AS count FROM devices GROUP BY status"
        ).fetchall())
        by_type = rows_to_list(conn.execute(
            "SELECT device_type, COUNT(*) AS count FROM devices GROUP BY device_type"
        ).fetchall())
        by_location = rows_to_list(conn.execute(
            """SELECT l.name AS location, COUNT(d.id) AS count
               FROM locations l LEFT JOIN devices d ON d.location_id = l.id
               GROUP BY l.id ORDER BY count DESC"""
        ).fetchall())
        total_locations = conn.execute("SELECT COUNT(*) AS c FROM locations").fetchone()["c"]
        total_ips = conn.execute("SELECT COUNT(*) AS c FROM ip_addresses").fetchone()["c"]

    return jsonify({
        "total_devices": total,
        "total_locations": total_locations,
        "total_ip_addresses": total_ips,
        "by_status": by_status,
        "by_type": by_type,
        "by_location": by_location,
    })


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


# ------------------------------------------------------- serve the frontend --
# Optional convenience: serving the static frontend from Flask itself so the
# whole app can run from a single `python app.py` with no separate server.

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def frontend_assets(filename):
    return send_from_directory(FRONTEND_DIR, filename)


if __name__ == "__main__":
    init_db()
    app.run(debug=True, host="0.0.0.0", port=5000)
