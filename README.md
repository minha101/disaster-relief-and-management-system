# Flood & Disaster Relief Coordination Management System (Pakistan)

Flask · SQLAlchemy · Flask-Login · Flask-Migrate · Flask-WTF · Bootstrap 5 · Chart.js · Leaflet/OpenStreetMap
**66 database tables**, 66 CRUD modules, 8 roles with database-backed RBAC.

> **Verification status – please read.** The package was written in an environment with no internet access, so
> Flask-SQLAlchemy / WTForms could not be installed there. Python syntax, Jinja templates, URL endpoints, the
> registry/model cross-references and the PDF generator were checked; the full app was **not executed**.
> Run `python smoke_test.py` first (see below): it builds a temporary database, loads sample data and opens every
> page and list/new/edit/detail/export route. Report any failure it prints and it can be fixed quickly.

## 1. Install & run (Windows, VS Code terminal / CMD)

```
cd disaster_relief_system
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python smoke_test.py
python seed.py
python run.py
```
Open http://127.0.0.1:5000 → you are redirected to **/setup** to create the Super Admin (password typed by you; nothing hardcoded).
Alternative: `set FLASK_APP=run.py` then `flask create-admin`.

`python seed.py` loads fictional demo data and prints one random demo password (also saved in `instance/demo_credentials.txt`).
Demo logins: `admin1@demo.example`, `dma1@demo.example`, `ngo1@demo.example`, `rescue1@demo.example`, `volunteer1@demo.example`, `donor1@demo.example`, `affected1@demo.example`, …
`python seed.py --reset` drops everything and rebuilds (development only).

Internet is needed in the browser for the CDN assets (Bootstrap, Chart.js, Leaflet, map tiles).

## 2. Database

* **SQLite (default, development):** nothing to configure; `instance/drms.db` is created automatically (`AUTO_CREATE_TABLES=true`).
* **MySQL (primary / production):**
  1. `CREATE DATABASE drms CHARACTER SET utf8mb4;` and a user with rights on it.
  2. In `.env`: `DATABASE_URL=mysql+pymysql://user:password@localhost:3306/drms?charset=utf8mb4` and `AUTO_CREATE_TABLES=false`
  3. ```
     set FLASK_APP=run.py
     flask db migrate -m "initial schema"
     flask db upgrade
     python seed.py
     ```
  (`migrations/` contains the Alembic/Flask-Migrate scaffold; the first `flask db migrate` generates the initial revision.)

## 3. What was built (your five "impressive" features)

| Feature | Where |
|---|---|
| **Live Disaster Map** | `/map` – incidents, SOS, relief camps, rescue teams, affected villages, hospitals, district flood alerts, evacuation routes; layer toggle; refreshes from the database every 30 s |
| **Emergency SOS** | `/sos` public form (map picker + browser GPS, honeypot, rate limit, CSRF) → tracking code `SOS-XXXXXXXX` (`/sos/track`) → instant in-app notification to authority/rescue roles; sidebar badge + toast (polls every 15 s) |
| **Smart Resource Allocation** | `/allocation` – per camp days-of-supply for food / water / medical vs occupancy, incoming allocations counted, greedy transfer suggestions from warehouses or camp surplus, “Propose” creates a draft `ResourceAllocation`; marking it *delivered* moves stock and writes ledger entries |
| **Disaster Analytics** | `/analytics` – district affected population, incidents, rescue progress, by type, trend, operations; filters; CSV |
| **Risk assessment** | `/risk` – transparent **heuristic index** (weights shown on page) from recorded incidents + active flood alerts, basis selectable (verified / +reported / +sample). It is labelled *not a prediction*: no model has been validated, `is_validated_model` is always false. Replace `app/services/risk.py` with a validated model before calling anything a prediction |

Other: dashboard with 10 live KPIs + 6 charts, drag-and-drop task board (`/tasks`), CSV import/export, PDF reports (`/reports`, plus PDF export of any list), uploads (images/PDF/DOCX/XLSX/TXT/CSV, magic-byte checked), audit log, in-app notifications, global search, public transparency page (`/transparency`, aggregates only).

## 4. Data honesty

* Every transactional row has `data_source`: **sample** (fictional, from seed.py), **reported** (entered by users), **verified** (promoted by authorised staff with “Mark verified”; sample rows can never be verified).
* Badges show it everywhere; a banner offers “Show real data only”; dashboards/maps/analytics/PDFs state the record mix.
* Nothing is fetched live: no GPS feed, weather, river-level or rescue telemetry. Team/ambulance positions and hospital beds are *manually entered* values shown with their timestamps. Weather/flood alerts require a source name and are entered by staff.
* Communication history is a log; the system does not send SMS or make calls.
* District coordinates are approximate centroids; sample villages are fictional. Emergency numbers 1122, 115, 15, 16 are public numbers flagged “confirm locally”.

## 5. Roles (RBAC)

Permissions are rows in `permissions` / `role_permissions` (`<module>.view|create|edit|delete|all`). `all` = sees every record; without it a user only sees/edits records they created.

| Role | Summary |
|---|---|
| Super Admin | everything incl. users, roles, audit, settings |
| Admin | all operational data + users; roles/audit read-only |
| Disaster Management Authority | full control of incidents, SOS, camps, teams, alerts, evacuation, risk; manage most others |
| NGO / Relief Organization | stock, allocations, distribution, volunteers, tasks, donations, campaigns, camp residents |
| Rescue Team | SOS handling, operations, assignments, tasks, camps (view) |
| Volunteer | tasks, own registration, view incidents/camps |
| Donor | own donations, campaigns, transparency |
| Affected Person | own SOS / household / complaints / feedback; camps & alerts (view) |

Edit the matrix in `app/services/rbac.py` and run `flask sync-rbac`. Self-registration offers only Affected / Volunteer / Donor.

## 6. Security

PBKDF2 password hashes + complexity policy, 5-failure lockout (15 min), CSRF on all forms and fetch calls, parameterised ORM queries, server-side validation of every field (types, ranges, choices, lengths, Pakistan coordinate box), upload whitelist + signature check + random names + 8 MB cap, CSV formula-injection guard, audit log, secrets from `.env` (a random dev key is stored in `instance/secret.key`), HttpOnly/SameSite cookies, security headers. For production: set `SECRET_KEY`, `SESSION_COOKIE_SECURE=true`, serve behind HTTPS, run with a WSGI server (on Windows e.g. `pip install waitress` then `waitress-serve --listen=127.0.0.1:8000 run:app`).

## 7. Structure

```
app/models      66 SQLAlchemy models (base, core, geo, incidents, operations, resources, people, health, system)
app/registry.py module registry (drives CRUD, RBAC, sidebar)
app/routes      auth, main (dashboard/api/files/search/transparency), crud (generic), gis, sos, tasks, intel, reports
app/services    rbac, audit, notify, formgen, hooks (business rules), stock, stats, risk, allocation, pdfgen, uploads, settings
app/forms       WTForms (auth, SOS)
app/templates, app/static
migrations/     Flask-Migrate scaffold      seed.py   smoke_test.py   config.py   run.py
```

## 8. Known limitations

* Real-time updates use polling (15–30 s), not WebSockets.
* Allocation counts only resources whose unit is `pack` (food), `litre` (water) or `kit` (medical); need-per-person figures are editable planning assumptions in *System Settings*, not official standards.
* Stock transactions and distribution records are immutable ledgers (create-only).
* Authenticated users can open an uploaded file if they know its random name; add per-record checks if files are sensitive.
