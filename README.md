# Rackline — Network Device Inventory System

A full-stack app for tracking network devices, their IP addresses, and their
physical/logical locations, with a REST API in the middle and a
purpose-built dashboard UI on top.

```
┌────────────────┐      REST/JSON       ┌──────────────────┐      SQL       ┌──────────────┐
│  Frontend (SPA) │  ────────────────▶  │   Flask API      │  ──────────▶   │  Database     │
│  HTML/CSS/JS    │  ◀────────────────  │   (Python)        │  ◀──────────   │  SQLite/      │
└────────────────┘                      └──────────────────┘                │  PostgreSQL/  │
                                                                             │  MySQL        │
                                                                             └──────────────┘
```

## Stack

| Layer     | Technology                                             |
|-----------|---------------------------------------------------------|
| Frontend  | HTML5, CSS3 (custom design system), vanilla JavaScript   |
| Backend   | Python + Flask, REST API                                 |
| Database  | SQLite by default (zero setup) — PostgreSQL/MySQL ready  |

No build step, no npm install required for the frontend — open it and it works.

## Project layout

```
network-inventory-system/
├── backend/
│   ├── app.py                 Flask app + all REST endpoints
│   ├── database.py            DB connection layer (SQLite/Postgres/MySQL)
│   ├── schema.sql              SQLite schema (used automatically)
│   ├── schema_postgresql.sql   Run this yourself if you switch to Postgres
│   ├── schema_mysql.sql        Run this yourself if you switch to MySQL
│   ├── seed_data.py            Optional: loads demo devices/locations
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
└── README.md
```

## Data model

**locations** — sites/buildings/rooms devices are racked in.
**devices** — one row per physical/virtual device (`hostname`, `device_type`,
manufacturer/model, serial, MAC, status, OS/firmware version, dates, notes,
and a foreign key to `locations`).
**ip_addresses** — one-to-many with devices, because a real device (a
firewall, especially) often carries more than one IP: a management address,
a WAN address, VLAN interfaces, etc.

```
locations 1 ──< devices 1 ──< ip_addresses
```

`device_type` is constrained to: router, switch, firewall, access_point,
server, load_balancer, printer, ups, other.
`status` is constrained to: active, maintenance, offline, decommissioned.

## Running it

Requires Python 3.9+. No external packages are required for the default
SQLite setup — only Flask itself.

```bash
cd backend
pip install -r requirements.txt      # installs Flask
python seed_data.py                  # optional: loads demo data
python app.py
```

Then open **http://localhost:5000** — Flask serves both the API (`/api/...`)
and the frontend from the same process, so there's nothing else to run.

If you'd rather serve the frontend separately (e.g. from a static file
server or another port) that works too — `js/app.js` calls the API with
relative paths (`/api/...`) and sets permissive CORS headers, so just make
sure requests reach the Flask process on port 5000, or update `API` in
`app.js` to point at wherever it's running.

## Switching to PostgreSQL or MySQL

The app ships on SQLite so it runs anywhere with no server to install. To
point it at a real relational server instead:

1. Install the driver:
   ```bash
   pip install psycopg2-binary   # for PostgreSQL
   # or
   pip install PyMySQL           # for MySQL
   ```
2. Create the database and run the matching schema file against it:
   ```bash
   psql -U youruser -d inventory -f backend/schema_postgresql.sql
   # or
   mysql -u youruser -p inventory < backend/schema_mysql.sql
   ```
3. Set environment variables before starting the app:
   ```bash
   export DB_ENGINE=postgresql        # or mysql
   export DB_HOST=localhost
   export DB_NAME=inventory
   export DB_USER=youruser
   export DB_PASSWORD=yourpassword
   python app.py
   ```

`backend/database.py` is the only file that knows about the underlying
engine — `app.py` and the frontend are unaffected either way.

## REST API reference

All endpoints return JSON. All list/detail responses on devices include
their nested `ip_addresses`.

| Method | Path                          | Description                                  |
|--------|-------------------------------|-----------------------------------------------|
| GET    | `/api/health`                 | Liveness check                                |
| GET    | `/api/stats`                  | Dashboard counts (by status/type/location)    |
| GET    | `/api/devices`                | List devices. Query params: `type`, `status`, `location_id`, `q` (free-text search across hostname/manufacturer/model/serial/MAC/IP) |
| GET    | `/api/devices/<id>`           | Single device with location + IPs             |
| POST   | `/api/devices`                | Create a device (`ip_addresses: []` optional) |
| PUT    | `/api/devices/<id>`           | Update a device (partial payload allowed)     |
| DELETE | `/api/devices/<id>`           | Delete a device (cascades its IP rows)        |
| POST   | `/api/devices/<id>/ips`       | Add an IP address to a device                 |
| DELETE | `/api/ips/<id>`               | Remove a single IP address                    |
| GET    | `/api/locations`              | List locations with a live `device_count`     |
| POST   | `/api/locations`              | Create a location                             |
| PUT    | `/api/locations/<id>`         | Update a location                             |
| DELETE | `/api/locations/<id>`         | Delete a location (devices there become unassigned) |

Example — create a device with an IP in one call:

```bash
curl -X POST http://localhost:5000/api/devices \
  -H "Content-Type: application/json" \
  -d '{
        "hostname": "edge-fw-02",
        "device_type": "firewall",
        "manufacturer": "Fortinet",
        "model": "FortiGate 200F",
        "status": "active",
        "location_id": 1,
        "ip_addresses": [{"ip_address": "10.0.0.253", "ip_type": "management"}]
      }'
```

Validation the API enforces: required `hostname`/`device_type`, enum checks
on `device_type`/`status`/`ip_type`, IPv4 format checking, MAC address
format checking, and uniqueness on hostname / serial number / IP address —
all returned as `400` with a descriptive `error` message rather than a
raw stack trace.

## Frontend

Single-page app, no framework or build tool:

- **Dashboard** — live counts by status, a breakdown by device type and by
  location, and an "needs attention" list of anything not `active`.
- **Devices** — searchable, filterable table (type / status / location);
  click a row to edit, including adding/removing its IP addresses inline;
  each row carries a small status-colored rail on its left edge.
- **Locations** — card grid showing every site with its live device count;
  click through to edit or delete.

The visual design intentionally borrows from network patch-panel/rack
vernacular (a graphite substrate, monospace for device data like IPs/MACs,
and three status colors — teal/amber/red — that map to real device states
rather than being decorative) instead of a generic dashboard template.

## Testing it worked

Every endpoint above was exercised end-to-end while building this (create,
read with filters/search, update, delete, invalid-input rejection,
duplicate-hostname rejection, invalid MAC/IP rejection, and 404 handling)
against the live Flask server before this was handed off — see the API
reference above for the exact request shapes that were verified.
