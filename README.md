# RalphAI: Unified Multi-Agent Marketing System

RalphAI is a consolidated intelligence and analytics framework for DoorDash and UberEats restaurant data. It serves as an orchestrator that unifies independent dashboards, reporting scripts, data parsers, and browser-automation agents into a single, cohesive architecture.

Rather than running multiple separate applications scattered across the workspace, everything is integrated as an **Agent** within RalphAI.

## Goal

Automate operator onboarding → data analysis → marketing recommendations → campaign creation (browser automation) → performance review in a closed loop, with optional human approval gates.

This repo **merges** two *styles* in one **`agents/`** tree:

- **Legacy JSON contract chain** — `orchestrator/flow_manager.py` imports `agents/*/contract_pipeline.py` (and `agents/ingestion/pipeline.py`) for the same shapes as `contracts/*.json`. Optional `python -m` / stdin: some `contract_pipeline` modules expose `__main__`.
- **TODC product pipeline** — `agents/*/agent.py`, `slack_bot/`, `data/operators/`, Pydantic `shared/models/` — DeepDive, MarketingReco, RalphAI, Campaign Review, Monthly Reporter, Slack commands.

Add new behavior under the relevant **`agents/<package>/`** only; do not reintroduce a top-level `apps/`.

---

## Principles

- **Independence** — Agent packages under `agents/` do not import each other; only `shared/`.
- **Contracts** — `contracts/*.json` document the micro-agent wire format; align Pydantic models when fields overlap.
- **Orchestration** — Event-driven handoffs; `event_router.py` + queue in production; `state_machine.py` for operator lifecycle.
- **Stateless processes** — Persist to `data/` (dev), S3/Postgres/Redis (prod); log `correlation_id` / `idempotency_key`.
- **Human-in-the-loop** — `flow_manager` gating + TODC `approval_status` on plans/reviews.

---

## Directory Layout

```
RalphAI/   # repo root
├── README.md
├── docker-compose.yml          # dev Redis (root)
├── .env.example
├── requirements.txt
├── contracts/                  # JSON Schema (micro-agent I/O)
├── agents/                     # deepdive (incl. monthly reporting + superapp), campaign_analyser, marketingreco, campaign_setup, campaign_review, ingestion
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

Every tool in RalphAI is housed in `agents/` and exposes a standardized interface. Agents can be launched programmatically via Python or using the global runner.

---

## Available Agents

*   **`the_super_app`**: The primary flagship React/Node frontend and Streamlit export API. Contains DoorDash export breakdown pivots (financial / marketing / sales-by-time), bucketing analysis, marketing (TODC vs Corporate) breakdowns, time slot analysis, A/B comparison screens, and Chart.js powered PDF report exports.
*   **`app2_0` & `app2_0_savvy`**: Legacy Python Streamlit dashboards (the predecessors to TheSuperApp). Maintained for historical reference and specific financial P&L rollups.
*   **`app3_0`**: The cloud-ready Streamlit app that introduced the comparison engine and headless runner. Functionality has been ported to TheSuperApp.
*   **`campaign_analyser`**: Python engine for 42-slot campaign analysis, zero-fire diagnosis, and slot performance.
*   **`markup_app`**: Simple HTTP server for static markup viewing.
*   **`reporting_browser_use_*`**: A suite of browser-automation scripts (various copies/variants like `browser`, `melt`, `new`, `savvy`) built using Python. These automate data extraction and report generation directly from the web.

---

## TODC Pipeline Agents

### DeepDive (`/deepdive`)

Pull/analyze ~90 days of DoorDash data; output includes `order_breakdown`, `revenue_metrics`, `recommendations_seed`, etc. Writes `data/operators/{id}/reports/deepdive.json`.

### MarketingReco (`/marketingreco`)

Consumes DeepDive; outputs `recommended_campaigns`, `approval_status`. Writes `marketing_plan.json`.

### Campaign setup — RalphAI (`/offers`, `/ads`)

Browser automation stubs; writes `campaigns/setup.json`, sets `review_scheduled_at`.

### Campaign review (`/marketingperf`)

Pre/post comparison; `recommendation` ∈ `/update`, `/delete`, `/new`, `/keep`. Writes `campaign_review.json`.

### Breakdown (The Super App)

Financial Summary table (App2.0 parity): Pre/Post/LY/YoY metrics from loaded DD + UE financial exports. Sidebar module **Breakdown** at `/agents/the-super-app?tab=breakdown`.

### Operator states (`state_machine.py`)

`NEW → DEEPDIVE_RUNNING → … → REVIEW_APPROVED → (loop)`.

---

## Lifecycle Comparison

| Concern | `flow_manager` + `contract_pipeline` | `agent.py` (TODC) |
|--------|---------------------|------------------|
| Step 1 | `ingestion` → `deepdive.contract_pipeline` (insights list) | DeepDive report JSON + disk |
| Step 2 | `marketingreco.contract_pipeline` (`campaign_plan` array) | MarketingReco + approval |
| Step 3 | `campaign_setup.contract_pipeline` (stub execution) | RalphAI `offers` / `ads` flows |
| Step 4 | `campaign_review.contract_pipeline` (`actions`) | Campaign review + `/marketingperf` |

Bridge when needed: map fields in an adapter (future) or standardize on TODC disk artifacts.

---

## Working with Data

All test and sample data has been scrubbed from the individual agent folders to enforce a single source of truth.

*   **Sample Data:** Located exclusively at `sample_data_bican/` in the root of this project.

---

## Quick Start

From the repo root:

```bash
cp .env.example .env   # fill in API keys / credentials as needed
./run.sh               # API :8000 + dashboard :5173 + builds Super App if needed
```

Open **http://localhost:5173** — the RalphAI workspace dashboard.

| Page | Route | Purpose |
|------|-------|---------|
| Dashboard | `/` | Run stats, recent activity, quick actions |
| Agents | `/agents` | Launch any agent workflow |
| MarketingReco | `/agents/marketingreco` | Offers + Ads plan generation |
| Offers / Ads | `/agents/offers`, `/agents/ads` | Browser automation setup |
| Campaign Review | `/agents/campaign-review` | Post-campaign performance |
| Breakdown | `/agents/the-super-app?tab=breakdown` | Financial Summary (Pre/Post/LY) |
| Health Check | `/agents/health-check` | WoW operator health + viz |
| The Super App | `/agents/the-super-app` | Full analytics UI (internal); Marketing tab includes export breakdown pivots |
| Jobs / Runs / Logs | `/jobs`, `/runs`, `/logs` | Saved jobs, history, activity |

Run tests:

```bash
PYTHONPATH=. python3 -m pytest tests/ -q
```

---

## Execution and Usage

We have eliminated all internal, per-app utility scripts. Everything is managed globally from the RalphAI root.

### 1. Running Agents

Use the global `run.sh` script to boot any agent. It dynamically loads the agent's `__init__.py` interface.

```bash
./run.sh <agent_name>
# Example: ./run.sh the_super_app
# Example: ./run.sh reporting_browser_use_browser
```

### 2. Legacy Micro-Pipeline

```bash
python3 -c "from orchestrator.flow_manager import run_deepdive_pipeline; print(run_deepdive_pipeline('op'))"
echo '{"command":"/deepdive","operator_id":"x"}' | python3 orchestrator/triggers.py
```

### 3. TODC Orchestrator

```bash
PYTHONPATH=. python3 -c "from orchestrator.todc_flow import run_onboarding_chain; print(run_onboarding_chain('op'))"
PYTHONPATH=. python3 -m pytest tests/ -q
```

### 4. Git Operations

A global `git.sh` script handles automated staging, committing, and pushing to `https://github.com/nithintodc/RalphAI.git`.

```bash
./git.sh "My commit message"
```

---

## Deployment

RalphAI supports two GCP deployment paths. Use **`./deploy.sh`** for TheSuperApp (primary product UI). Use the manual steps below when deploying the full **FastAPI + dashboard orchestrator** (`api/main.py` + `dashboard/`) as a single Cloud Run service.

### TheSuperApp (recommended)

The global `deploy.sh` script deploys the primary TODC analytics interface:

- **Backend** → GCP Cloud Run (`todc-export-api`, built from `agents/the_super_app/streamlit_app`)
- **Frontend** → Firebase Hosting (`agents/the_super_app/app`)

**Prerequisites:** GCP account with billing, `gcloud` CLI (authenticated), `npm`, and `firebase-tools`. No local Docker required — Cloud Run builds via `--source`.

```bash
# Full deploy (backend + frontend)
./deploy.sh <GCP_PROJECT_ID>

# Or set project via env
GCP_PROJECT=my-proj ./deploy.sh

# Partial deploys
./deploy.sh <GCP_PROJECT_ID> --backend-only
./deploy.sh <GCP_PROJECT_ID> --frontend-only
```

**Backend secrets and env** (handled automatically by `deploy.sh`):

| Item | Source |
|---|---|
| `GCP_SERVICE_ACCOUNT_JSON` | Secret Manager (`todc-export-sa-json`) — set `SA_JSON=path/to/json` if not auto-detected |
| `AIRTABLE_PAT` | Secret Manager (optional, from `.env`) |
| `GOOGLE_SHARED_DRIVE_NAME` | Env var (default: `Data-Analysis-Uploads`) |
| `AIRTABLE_BASE_ID`, `AIRTABLE_TABLE_ID` | Env vars (optional, from `.env`) |

**Useful env overrides:**

```bash
export GCP_REGION=us-central1
export SERVICE_NAME=todc-export-api
export FIREBASE_PROJECT=my-proj
export SA_JSON=agents/the_super_app/streamlit_app/todc-marketing-XXXX.json
```

---

### Full orchestrator on GCP (Path A — recommended)

**Git → GitHub Actions → Cloud Build → Cloud Run** — step-by-step checklist:

**[docs/DEPLOY_PATH_A.md](docs/DEPLOY_PATH_A.md)**

Quick start:

```bash
export GCP_PROJECT_ID=your-project-id
./scripts/gcp-bootstrap.sh
# Add GitHub secrets GCP_PROJECT_ID, GCP_REGION, GCP_SA_KEY (see doc)
git push origin main
```

Deploy the workspace API and React dashboard to existing Cloud Run **`todc-reporting-app`** (`todc-marketing`, `us-central1`). Each CI deploy replaces the service image; prior revisions remain for rollback.

#### Architecture

```
                    ┌─────────────────────┐
                    │   Cloud Load Balancer│
                    │   (HTTPS + domain)   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │     Cloud Run       │
                    │  ralphai-api        │
                    │  (API + Dashboard)  │
                    └──┬──────────────┬───┘
                       │              │
          ┌────────────▼───┐   ┌──────▼──────────┐
          │  Memorystore   │   │  Cloud Storage   │
          │  (Redis)       │   │  (run artifacts) │
          └────────────────┘   └─────────────────┘
                    │
          ┌────────▼─────────┐
          │  Secret Manager  │
          │  (API keys, env) │
          └──────────────────┘
```

**Services used:**

- **Cloud Run** — FastAPI backend + static React dashboard (single container)
- **Artifact Registry** — Docker image storage
- **Memorystore for Redis** — managed Redis
- **Cloud Storage (GCS)** — persistent storage for run data/reports
- **Secret Manager** — API keys and credentials
- **Cloud Build** — CI/CD image builds (optional alternative to local Docker)
- **VPC Connector** — connects Cloud Run to Memorystore (private network)

**Prerequisites:** GCP account with billing, `gcloud` CLI, Node.js 18+, Python 3.12+. Docker is optional if you use Cloud Build instead of local `docker build`.

#### Quick setup

```bash
export GCP_PROJECT="your-project-id"
export GCP_REGION="us-central1"
```

#### 1. Enable APIs

```bash
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  redis.googleapis.com \
  vpcaccess.googleapis.com \
  --project=$GCP_PROJECT
```

#### 2. Create Artifact Registry repository

```bash
gcloud artifacts repositories create ralphai \
  --repository-format=docker \
  --location=$GCP_REGION \
  --project=$GCP_PROJECT
```

#### 3. Create secrets

```bash
# Required
echo -n "your-anthropic-key" | gcloud secrets create ANTHROPIC_API_KEY \
  --data-file=- --project=$GCP_PROJECT

# Optional (Slack integration)
echo -n "xoxb-..." | gcloud secrets create SLACK_BOT_TOKEN \
  --data-file=- --project=$GCP_PROJECT
echo -n "..." | gcloud secrets create SLACK_SIGNING_SECRET \
  --data-file=- --project=$GCP_PROJECT
echo -n "xapp-..." | gcloud secrets create SLACK_APP_TOKEN \
  --data-file=- --project=$GCP_PROJECT
```

Update a secret later:

```bash
echo -n "new-value" | gcloud secrets versions add ANTHROPIC_API_KEY --data-file=-
```

#### 4. Create VPC connector (for Redis)

```bash
gcloud compute networks vpc-access connectors create ralphai-connector \
  --region=$GCP_REGION \
  --range=10.8.0.0/28 \
  --project=$GCP_PROJECT
```

#### 5. Create Memorystore Redis instance

```bash
gcloud redis instances create ralphai-redis \
  --size=1 \
  --region=$GCP_REGION \
  --redis-version=redis_7_0 \
  --tier=basic \
  --project=$GCP_PROJECT

REDIS_HOST=$(gcloud redis instances describe ralphai-redis \
  --region=$GCP_REGION --format='value(host)' --project=$GCP_PROJECT)
```

#### 6. Create GCS bucket for run data

```bash
gsutil mb -l $GCP_REGION gs://${GCP_PROJECT}-ralphai-data
```

#### 7. Build and push Docker image

Build the dashboard first, then the API container (`infra/gcp/Dockerfile.api` bundles `dashboard/dist/` into FastAPI):

```bash
gcloud auth configure-docker ${GCP_REGION}-docker.pkg.dev

cd dashboard && npm ci && npm run build && cd ..

IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/ralphai/ralphai-api:$(git rev-parse --short HEAD)"
docker build -f infra/gcp/Dockerfile.api -t $IMAGE .
docker push $IMAGE
```

Or use Cloud Build (no local Docker):

```bash
gcloud builds submit . \
  --config=infra/gcp/cloudbuild.yaml \
  --substitutions=_IMAGE="$IMAGE" \
  --project=$GCP_PROJECT
```

#### 8. Deploy to Cloud Run

```bash
gcloud run deploy ralphai-api \
  --image=$IMAGE \
  --region=$GCP_REGION \
  --platform=managed \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=2 \
  --timeout=3600 \
  --max-instances=5 \
  --min-instances=0 \
  --vpc-connector=ralphai-connector \
  --set-env-vars="REDIS_URL=redis://${REDIS_HOST}:6379/0,LOG_LEVEL=INFO,GCS_BUCKET=${GCP_PROJECT}-ralphai-data" \
  --set-secrets="ANTHROPIC_API_KEY=ANTHROPIC_API_KEY:latest,SLACK_BOT_TOKEN=SLACK_BOT_TOKEN:latest,SLACK_SIGNING_SECRET=SLACK_SIGNING_SECRET:latest" \
  --project=$GCP_PROJECT
```

The single-container approach serves the built React dashboard from FastAPI static mounts — no separate frontend CDN required.

#### Orchestrator environment variables

| Variable | Source | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | Secret Manager | Yes |
| `REDIS_URL` | Env var (Memorystore IP) | Yes |
| `LOG_LEVEL` | Env var | No (default: INFO) |
| `SLACK_BOT_TOKEN` | Secret Manager | No |
| `SLACK_SIGNING_SECRET` | Secret Manager | No |
| `SLACK_APP_TOKEN` | Secret Manager | No |
| `GCS_BUCKET` | Env var | Recommended |
| `PORT` | Set by Cloud Run | Automatic |

#### Cost estimates (monthly)

| Service | Config | Estimate |
|---|---|---|
| Cloud Run | 2 vCPU, 2GB, min 0 | $0–50 (pay per use) |
| Memorystore Redis | Basic, 1GB | ~$35 |
| Artifact Registry | Image storage | ~$1 |
| Cloud Storage | Run data | ~$1–5 |
| Secret Manager | 5 secrets | <$1 |
| VPC Connector | Serverless | ~$7 |
| **Total** | | **~$45–95/mo** |

Cloud Run scale-to-zero keeps costs low when idle.

#### Custom domain (optional)

```bash
gcloud run domain-mappings create \
  --service=ralphai-api \
  --domain=ralph.yourdomain.com \
  --region=$GCP_REGION
# Follow the DNS verification instructions printed
```

#### Monitoring and updates

```bash
# View logs
gcloud run services logs read ralphai-api --region=$GCP_REGION --limit=50

# Tail logs live
gcloud run services logs tail ralphai-api --region=$GCP_REGION
```

Cloud Run provides request latency, error metrics, structured logging, and auto-scaling.

To redeploy after code changes, repeat steps 7–8 (rebuild image, deploy). To rollback:

```bash
gcloud run revisions list --service=ralphai-api --region=$GCP_REGION

gcloud run services update-traffic ralphai-api \
  --to-revisions=ralphai-api-REVISION=100 \
  --region=$GCP_REGION
```

#### Troubleshooting

| Issue | Fix |
|---|---|
| Container fails to start | Check `gcloud run services logs read` for Python import errors |
| Redis connection refused | Verify VPC connector is attached and Redis IP is correct |
| Secrets not found | Ensure Cloud Run service account has `secretmanager.secretAccessor` role |
| 504 timeout on long agent runs | Increase `--timeout` (max 3600s). Consider async task queue for long jobs |
| Dashboard not loading | Verify `dashboard/dist/` was built before Docker build |

For VM-based deployment and browser-automation caveats, see `docs/GCP_DEPLOYMENT.md`.

---

## Technology Stack

| Area | Options |
|------|---------|
| Slack | Bolt (`slack_bot/`) |
| LLM | Anthropic (prompts under `agents/*/prompts/`) |
| Browser | browser-use / Playwright (`agents/campaign_setup/`) |
| Queue / state | Redis (`docker-compose.yml`), then SQS/Temporal |
| Infra | `infra/terraform`, `infra/docker` |

---

## Release Checklist

Before shipping a RalphAI iteration:

1. Copy `.env.example` → `.env` and set required secrets (`ANTHROPIC_API_KEY`, DoorDash credentials, optional Slack/Airtable).
2. Run `./run.sh` locally — confirm dashboard at `:5173` and API at `:8000`.
3. Smoke-test key agent pages: MarketingReco, Health Check, The Super App (Breakdown tab).
4. Run `PYTHONPATH=. python3 -m pytest tests/ -q` (expect all green; one browser-use discovery test may skip locally).
5. Deploy with `./deploy.sh <GCP_PROJECT_ID>` or the full orchestrator steps in **Deployment** above.
6. Rollback: redeploy a prior Cloud Run revision or revert git and redeploy.

---

## Roadmap / Pending Work

### Stabilize API and Slack

- Harden `api/main.py` endpoints with input validation, consistent error payloads, and agent timeout handling.
- Complete Slack command behavior for DeepDive and MarketingReco with clear success/failure user messages.
- Add end-to-end test coverage for API + orchestrator handoff on updated agent paths.

### Tests and quality

- Expand DeepDive and MarketingReco tests for metric hierarchy edge cases and ads planner fallbacks.
- Fix `tests/test_doordash_download_discovery.py` import isolation for `reporting_browser_use` (currently skips when shadowed by repo `agents/`).

### Dashboard UX

- Add loading, empty, and error states on any agent pages still missing them.
- Surface agent run status/progress in UI (queued / running / success / failed).
- Ensure page-level forms match API contracts for Ads and Offers workflows.

### Platform and agents

- Harden agent error handling — retries, timeouts, structured error responses.
- Complete Slack bot wiring — all command stubs invoke the correct agents.
- Add UberEats and GrubHub support to browser automation agents.
- Build operator onboarding wizard in the dashboard.
- User authentication and role-based access in the dashboard.
- Rate limiting and queue management for concurrent agent runs.
- Data validation layer for CSV/Excel uploads.
- Agent performance monitoring (success rates, latency, errors).
- Multi-tenant data isolation and SSO/OAuth for SaaS mode.
- Campaign performance alerting (ROAS threshold drops).

### Operations

- CI/CD pipeline (GitHub Actions) for tests and deployment.
- Staging environment on GCP for pre-production testing.
- Runbook for common failure modes and recovery.
- Monitoring and alerting (Datadog / Prometheus+Grafana).
- Automated backups and operator data migration scripts.
- Production Redis queue wiring (replace flat-file dev state).
- Log aggregation and search.

### Documentation

- API documentation for all agent endpoints.
- Operator user guide with screenshots.
- Agent contract JSON schema with examples.
- Architecture decision records (ADRs).
- Troubleshooting guide for common agent failures.
- Document all environment variables (see `.env.example`).

### Productization

- SaaS billing (Stripe), self-service signup, marketing landing page.
- Demo environment with sample data (`sample_data_bican/`).
- Product analytics (PostHog / Mixpanel).

### Architecture (future)

- Single adapter mapping `contracts/*.json` ↔ Pydantic `shared/models/`.
- Replace flat files with Postgres + object storage.
- Wire `slack_bot/app.py` handlers to production queues.
