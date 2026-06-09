# SimLifecycle Agent

**Simulation Data Lifecycle Management System** — a policy-driven prototype that
automatically tiers simulation datasets across **Hot → Warm → Cold** storage based
on access patterns and inactivity, keeps a metadata catalog so archived data stays
discoverable, supports on-demand restore, and gives administrators a dashboard for
utilisation, cost savings, and policy compliance.

This is a self-contained **working prototype**: storage tiers are simulated as local
directories, the catalog uses SQLite, and a deterministic policy engine drives all
tiering decisions (no LLM, no cloud account required).

---

## Architecture

```
Engineer / Admin ──► React dashboard (Vite)
                           │  /api proxy
                           ▼
                     FastAPI backend
   ┌───────────────────────────────────────────────┐
   │ routers: datasets · policies · lifecycle · dash │
   │ services: catalog · policy_engine · lifecycle   │
   │           · metrics                             │
   │ scheduler (APScheduler) ── runs lifecycle scan  │
   │ storage backend (Hot/Warm/Cold local dirs)      │
   │ SQLite catalog + audit events                   │
   └───────────────────────────────────────────────┘
```

- **`catalog`** is the single writer of dataset metadata; every create/move/restore
  emits an append-only `LifecycleEvent` (guarantees catalog accuracy + audit trail).
- **`policy_engine`** is pure & deterministic — easy to unit-test.
- **`lifecycle_agent`** = detect inactive (UC6) + move tiers (UC7); invoked by both
  the on-demand API and the background scheduler.
- **`storage/backend.py`** abstracts physical placement behind a `StorageBackend`
  interface so a real S3/Glacier driver can drop in later.

### Use-case coverage
| UC | Description | Where |
|----|-------------|-------|
| 1 | Create data → hot | `POST /datasets` |
| 2 | Access active data | `POST /datasets/{id}/access` |
| 3 | Retrieve/restore archived | `POST /datasets/{id}/restore` |
| 4 | Define policies + exceptions | `/policies`, `/exceptions`, `/datasets/{id}/critical` |
| 5 | Monitor & report | `GET /dashboard/metrics`, `/dashboard/events` |
| 6 | Detect inactive | `GET /lifecycle/candidates` |
| 7 | Move across tiers | `POST /lifecycle/run` + scheduler |
| 8 | Maintain metadata/catalog | `catalog` service + `GET /datasets` |

---

## Time simulation (important for demos)

Real 30/90-day thresholds can't be observed live, so one **simulated "day" equals
`SIMLC_TIME_UNIT_SECONDS` real seconds** (default `1.0`). With the default, a 30-day
threshold elapses in 30 seconds. Seed data is also backdated so a scan has work to do
immediately. Set `SIMLC_TIME_UNIT_SECONDS=86400` for real-time behaviour.

---

## Running

### 1. Backend (port 8000)

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

On first start it creates the SQLite DB + `storage/{hot,warm,cold}` dirs and seeds
demo datasets and default policies. API docs at <http://localhost:8000/docs>.

### 2. Frontend (port 5173)

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. The dev server proxies `/api/*` to the backend.

### Useful environment variables (prefix `SIMLC_`)
| Var | Default | Meaning |
|-----|---------|---------|
| `SIMLC_TIME_UNIT_SECONDS` | `1.0` | Real seconds per simulated day |
| `SIMLC_SCAN_INTERVAL_SECONDS` | `20` | Background auto-scan cadence |
| `SIMLC_SEED_ON_STARTUP` | `true` | Seed demo data if DB empty |

---

## Try it (maps to success criteria)

1. **Dashboard** — see all datasets start in hot; note baseline cost & compliance.
2. **Run Lifecycle Scan** (Dashboard or Events) — inactive datasets move Hot→Warm→Cold;
   reclaimed capacity, cost savings, and compliance % update; Events shows the moves.
3. **Catalog** — create a dataset (lands in hot), "Access" one (refreshes recency),
   "Restore" an archived one back to hot, "Mark critical" to exempt it.
4. **Policies** — adjust thresholds / disable a policy / add an exception, then rescan.
5. **Zero-intervention** — leave it running; the scheduler tiers data automatically.

---

## Tests

```bash
cd backend && .venv/bin/python -m pytest -q
```

Covers the deterministic policy engine: threshold boundaries, tier cascades,
critical/exception exemptions, and disabled policies.
