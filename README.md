# RalphAI

Multi-agent marketing automation for TODC: JSON contracts, `agents/` (TODC + legacy contract pipelines), Slack, tests, and infra — all at this repo root.

**Web UI:** `dashboard/` — Vite + React SaaS shell (`cd dashboard && npm install && npm run dev`).

---

# TODC / Multi-Agent Marketing System (unified)

Single project combining:

1. **JSON contracts + `agents/*/contract_pipeline.py`** — legacy wire format used by `flow_manager` + execution gating (same packages as TODC; no separate `apps/` tree).
2. **TODC `agents/*/agent.py`** — DeepDive, MarketingReco, Campaign Setup (Clawbot), Campaign Review, Monthly Reporter with Pydantic models and `data/operators/{id}/` artifacts.
3. **Slack** — `slack_bot/` (Bolt) command stubs wired to `agents/`.
4. **Orchestration** — `flow_manager` / `triggers` (legacy chain), `state_machine` + `event_router` (TODC), `todc_flow` (TODC Python API), merged `scheduler`.

## Layout

| Path | Role |
|------|------|
| `contracts/` | JSON Schema I/O for micro-agent protocol |
| `agents/` | One package per capability: `agent.py` (TODC disk artifacts), `contract_pipeline.py` where needed (flow_manager JSON chain), `ingestion/` for pull step |
| `shared/` | `config/`, `models/`, `utils/`, `logger.py` |
| `orchestrator/` | Pipelines, state machine, event routing, schedulers |
| `slack_bot/` | Slash-command handlers |
| `data/` | Local operator artifacts (`raw/`, `reports/`, `campaigns/`) |
| `infra/` | Docker images, Terraform, queue docs |
| `tests/` | Pytest |

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env   # optional

# Legacy JSON pipeline (flow_manager + contract_pipeline modules)
python3 -c "from orchestrator.flow_manager import run_deepdive_pipeline; print(run_deepdive_pipeline('op'))"

# TODC chain (agents + disk artifacts)
PYTHONPATH=. python3 -c "from orchestrator.todc_flow import run_onboarding_chain; print(run_onboarding_chain('op'))"

# Tests
PYTHONPATH=. python3 -m pytest tests/ -q
```

## Docker / Redis

```bash
docker compose up -d redis
```

See `infra/docker/` for additional image patterns.

## Dashboard (UI)

```bash
cd dashboard && npm install && npm run dev
```

SaaS-style shell at `http://localhost:5173` — Dashboard, Agents, Runs, Settings, Logs. See [dashboard/README.md](./dashboard/README.md).

**Monthly Reporter (App2.0 analytics)** — UI at `/agents/monthly-reporter`. Start the API so uploads and run history work (Vite proxies `/api` to port 8000):

```bash
pip install -r requirements.txt
PYTHONPATH=. uvicorn api.main:app --reload --port 8000
```

Report engine code lives under `agents/monthly_reporter/cloud_app/` (ported from `App2.0-cloud-app/`). Optional Google Drive uploads use a service-account JSON placed beside the app (see `App2.0-cloud-app/CREDENTIALS_SETUP.md`).

## Docs

- [planning.md](./planning.md) — full architecture and agent definitions.
