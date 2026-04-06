# Unified Multi-Agent Marketing System — Planning

## Goal

Automate operator onboarding → data analysis → marketing recommendations → campaign creation (browser automation) → performance review in a closed loop, with optional human approval gates.

This repo **merges** two *styles* in one **`agents/`** tree:

- **Legacy JSON contract chain** — `orchestrator/flow_manager.py` imports `agents/*/contract_pipeline.py` (and `agents/ingestion/pipeline.py`) for the same shapes as `contracts/*.json`. Optional `python -m` / stdin: some `contract_pipeline` modules expose `__main__`.
- **TODC product pipeline** — `agents/*/agent.py`, `slack_bot/`, `data/operators/`, Pydantic `shared/models/` — DeepDive, MarketingReco, Clawbot, Campaign Review, Monthly Reporter, Slack commands.

Add new behavior under the relevant **`agents/<package>/`** only; do not reintroduce a top-level `apps/`.

---

## Principles

- **Independence** — Agent packages under `agents/` do not import each other; only `shared/`.
- **Contracts** — `contracts/*.json` document the micro-agent wire format; align Pydantic models when fields overlap.
- **Orchestration** — Event-driven handoffs; `event_router.py` + queue in production; `state_machine.py` for operator lifecycle.
- **Stateless processes** — Persist to `data/` (dev), S3/Postgres/Redis (prod); log `correlation_id` / `idempotency_key`.
- **Human-in-the-loop** — `flow_manager` gating + TODC `approval_status` on plans/reviews.

---

## Directory layout (unified)

```
RalphAI/   # repo root
├── README.md
├── planning.md
├── docker-compose.yml          # dev Redis (root)
├── .env.example
├── requirements.txt
├── contracts/                  # JSON Schema (micro-agent I/O)
├── agents/                     # deepdive, marketingreco, campaign_setup, campaign_review, monthly_reporter, ingestion
│                               # + contract_pipeline.py where flow_manager needs legacy JSON I/O
├── orchestrator/
│   ├── flow_manager.py         # imports agents/*/contract_pipeline + ingestion
│   ├── triggers.py             # command → dispatch (stdin)
│   ├── todc_flow.py            # agents/ Python API
│   ├── state_machine.py        # operator lifecycle
│   ├── event_router.py         # next-step job descriptors
│   └── scheduler.py            # legacy tick + TODC review_due_at
├── shared/
│   ├── config/                 # Settings, constants, data_root
│   ├── models/                 # Pydantic (TODC reports)
│   ├── utils/                  # json_io, dates, parsers, slack stub
│   └── logger.py
├── slack_bot/                  # Bolt app + commands
├── data/operators/{id}/        # raw, reports, campaigns
├── infra/                      # docker/, terraform/, queue/
└── tests/
```

---

## Lifecycle comparison

| Concern | `flow_manager` + `contract_pipeline` | `agent.py` (TODC) |
|--------|---------------------|------------------|
| Step 1 | `ingestion` → `deepdive.contract_pipeline` (insights list) | DeepDive report JSON + disk |
| Step 2 | `marketingreco.contract_pipeline` (`campaign_plan` array) | MarketingReco + approval |
| Step 3 | `campaign_setup.contract_pipeline` (stub execution) | Clawbot `offers` / `ads` flows |
| Step 4 | `campaign_review.contract_pipeline` (`actions`) | Campaign review + `/marketingperf` |

Bridge when needed: map fields in an adapter (future) or standardize on TODC disk artifacts.

---

## Running

**Legacy micro-pipeline**

```bash
python3 -c "from orchestrator.flow_manager import run_deepdive_pipeline; print(run_deepdive_pipeline('op'))"
echo '{"command":"/deepdive","operator_id":"x"}' | python3 orchestrator/triggers.py
```

**TODC**

```bash
PYTHONPATH=. python3 -c "from orchestrator.todc_flow import run_onboarding_chain; print(run_onboarding_chain('op'))"
PYTHONPATH=. python3 -m pytest tests/ -q
```

---

## TODC agent summary (detail)

### DeepDive (`/deepdive`)

Pull/analyze ~90 days of DoorDash data; output includes `order_breakdown`, `revenue_metrics`, `recommendations_seed`, etc. Writes `data/operators/{id}/reports/deepdive.json`.

### MarketingReco (`/marketingreco`)

Consumes DeepDive; outputs `recommended_campaigns`, `approval_status`. Writes `marketing_plan.json`.

### Campaign setup — Clawbot (`/offers`, `/ads`)

Browser automation stubs; writes `campaigns/setup.json`, sets `review_scheduled_at`.

### Campaign review (`/marketingperf`)

Pre/post comparison; `recommendation` ∈ `/update`, `/delete`, `/new`, `/keep`. Writes `campaign_review.json`.

### Monthly Reporter

Rolls up monthly KPIs and narrative summary from prior DeepDive / review artifacts (stub writes `reports/monthly_report_YYYY-MM.json` under `data/operators/{id}/`).

### Operator states (`state_machine.py`)

`NEW → DEEPDIVE_RUNNING → … → REVIEW_APPROVED → (loop)`.

---

## Technology stack

| Area | Options |
|------|---------|
| Slack | Bolt (`slack_bot/`) |
| LLM | Anthropic (prompts under `agents/*/prompts/`) |
| Browser | browser-use / Playwright (`agents/campaign_setup/`) |
| Queue / state | Redis (`docker-compose.yml`), then SQS/Temporal |
| Infra | `infra/terraform`, `infra/docker` |

---

## Future work

- Single adapter mapping `contracts/*.json` ↔ Pydantic `shared/models/`.
- Replace flat files with Postgres + object storage.
- Wire `slack_bot/app.py` handlers to production queues.
