# SimLifecycle Agent

**Simulation Data Lifecycle Management System** — a policy-driven prototype that
automatically tiers simulation datasets across **Hot → Warm → Cold** storage based
on access patterns and inactivity, keeps a metadata catalog so archived data stays
discoverable, supports on-demand restore, and gives administrators a dashboard for
utilisation, cost savings, and policy compliance.

This is a self-contained **working prototype**: storage tiers are simulated as local
directories and the catalog uses SQLite. An **AI storage manager** (Claude Opus 4.8)
makes the tiering decisions — for each dataset it weighs **policy + how critical the
data is + cost/GB savings** and decides whether to keep or tier it down, with a
natural-language rationale. With no API key it falls back to a deterministic
heuristic that follows the same three-factor reasoning, so the prototype always runs.

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
- **`policy_engine`** is pure & deterministic — produces the *policy signal* and
  enforces hard exemptions; easy to unit-test.
- **`ai_advisor`** is the agentic decision layer: it feeds policy signal + dataset
  criticality + per-tier cost into Claude (Opus 4.8, structured output) and returns
  a keep/move recommendation + rationale per dataset. Heuristic fallback when no key.
- **`lifecycle_agent`** asks the advisor what to do, then executes the moves and
  records the AI rationale on each event; invoked by the API and the scheduler.
- **`storage/backend.py`** abstracts physical placement behind a `StorageBackend`
  interface so a real S3/Glacier driver can drop in later.

### The AI storage manager

Tiering is no longer a fixed rule — the agent reasons over three factors per dataset:

1. **Policy signal** — is it inactive past threshold, and what tier does policy suggest?
2. **Criticality** — `criticality_score` (0–100), `business_value`, `data_classification`.
   High-criticality data is kept fast even when inactive (a slow restore at a critical
   moment outweighs the storage saving).
3. **Cost/GB** — the monthly savings a move would realise; large low-value inactive
   datasets are the best move candidates and may skip straight to cold.

Hard exemptions (critical flag / project exceptions) are a guardrail — exempt datasets
are never even offered to the advisor. The **AI Advisor** page shows every
recommendation with its rationale; the engine badge shows whether live Claude or the
heuristic is active.

**Enable live Claude:** `export ANTHROPIC_API_KEY=sk-ant-...` before starting the
backend. Without it, the heuristic runs (same decision shape, no LLM call).

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

Every start drops + recreates the SQLite schema, clears the simulated
`storage/{hot,warm,cold}` dirs, and reseeds demo data (so the schema always matches
the models — no migrations). Set `SIMLC_RESET_ON_STARTUP=false` to persist data
across restarts. API docs at <http://localhost:8000/docs>.

To use **live Claude** for tiering decisions: `export ANTHROPIC_API_KEY=sk-ant-...`
before starting the backend. Without it, the deterministic heuristic runs.

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
| `SIMLC_SCAN_INTERVAL_SECONDS` | `5` | Background auto-scan cadence |
| `SIMLC_RESET_ON_STARTUP` | `true` | Drop + recreate schema and clear storage each boot |
| `SIMLC_SEED_ON_STARTUP` | `true` | Seed demo data if DB empty |
| `SIMLC_USE_AI` | `true` | Use the AI advisor (falls back to heuristic without a key) |
| `SIMLC_AI_MODEL` | `claude-opus-4-8` | Model for the AI advisor |
| `ANTHROPIC_API_KEY` | — | Enables live Claude; unset → heuristic fallback |

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
