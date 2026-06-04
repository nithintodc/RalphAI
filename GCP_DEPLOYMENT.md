# RalphAI — Google Cloud Platform deployment guide

This document walks through deploying **RalphAI** so your team can use the **dashboard** and **FastAPI** (`api/main.py`) on GCP. It covers a recommended architecture, prerequisites, concrete commands, team access, and important caveats (especially **browser automation**).

---

## What you are deploying

| Piece | Role |
|--------|------|
| **FastAPI** (`api/main.py`) | REST API: DeepDive, MarketingReco, Campaign Review, Offers, Ads, Monthly Reporter, account directory, run history. |
| **React dashboard** (`dashboard/`) | SPA; dev server proxies `/api` to port 8000. In production you must put **the UI and `/api` on the same origin** (reverse proxy) **or** configure a public API URL + CORS (code change). |
| **`agents/reporting_browser_use/`** | Browser-use DoorDash workflow (`main.py` + nested `agents/`). Used by Offers/Ads from the API (subprocess `cwd`). Must be **in the container / VM filesystem** with the rest of the repo. |
| **`TODC_DATA_DIR` / `data/`** | Operator artifacts and run outputs. On **Cloud Run** the filesystem is **ephemeral** unless you attach **Cloud Storage** (or another volume) and point `TODC_DATA_DIR` there. |

---

## Recommended architectures

### Option A — Fastest path for a small team: one Compute Engine VM

- **One VM** (e.g. `e2-standard-4` or larger if you run heavy jobs), **Docker Compose** or **systemd** running:
  - **nginx** (or Caddy): TLS, serve `dashboard/dist`, proxy `/api` → uvicorn.
  - **uvicorn** API (or gunicorn+uvicorn workers).
- **Pros:** Simple, persistent disk for `data/`, easier **Chrome / browser-use** for Offers & Ads.
- **Cons:** You manage OS patches, scaling, and backups.

### Option B — Managed API + static UI (good Cloud-native default)

- **Cloud Run** (or Cloud Run **with GPU** only if you later need it): runs **only the FastAPI** container.
- **Firebase Hosting** or **Cloud Storage + HTTPS Load Balancer**: serves the **built** dashboard SPA with **rewrite rules** so `/api/*` is forwarded to Cloud Run.
- **Pros:** Autoscaling API, no servers to patch for the API tier.
- **Cons:** **Ephemeral disk** on Cloud Run — configure **Cloud Storage** (or Filestore) for `TODC_DATA_DIR` and `data/runs/**`. **Browser automation** inside Cloud Run is **hard** (no display, Chrome, CAPTCHAs); often **Offers/Ads** stay on a **VM** or dedicated worker.

### Option C — API only on Cloud Run + internal team VPN / IAP

- Same as B, but access is locked down with **Identity-Aware Proxy (IAP)** on the HTTPS load balancer or **VPC** + internal ingress.

Pick **A** if you need **Offers/Ads browser flows** day one with minimal fighting Chrome in containers. Pick **B** if the team mostly uses **upload-based** agents (DeepDive zip, MarketingReco manual, Campaign Review manual) and you will add **GCS** for persistence.

---

## Prerequisites

1. **Google Cloud account** with **billing** enabled.
2. **gcloud CLI** installed and authenticated:
   ```bash
   gcloud auth login
   gcloud config set project YOUR_PROJECT_ID
   ```
3. **Docker** (local or use **Cloud Build**).
4. **Node.js 20+** (to build the dashboard locally or in CI).

---

## Phase 1 — Enable APIs and create artifact registry

```bash
export PROJECT_ID=your-project-id
export REGION=us-central1   # or your preferred region

gcloud config set project "$PROJECT_ID"

gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  compute.googleapis.com \
  iam.googleapis.com
```

Create a Docker repository:

```bash
gcloud artifacts repositories create ralphai \
  --repository-format=docker \
  --location="$REGION" \
  --description="RalphAI images"
```

---

## Phase 2 — Build and push the API image

Ensure **`PROJECT_ID`** and **`REGION`** are set before defining **`IMAGE`** (otherwise the tag will be invalid).

From the **repository root** (where `requirements.txt` and `api/` live):

```bash
export IMAGE="$REGION-docker.pkg.dev/$PROJECT_ID/ralphai/ralphai-api:$(git rev-parse --short HEAD 2>/dev/null || echo manual)"

docker build -f infra/gcp/Dockerfile.api -t "$IMAGE" .
docker push "$IMAGE"
```

If you see **`command not found: docker`** (common on Mac without Docker Desktop), either install [Docker Desktop for Mac](https://docs.docker.com/desktop/setup/install/mac-install/) or use **Cloud Build** below so nothing runs locally.

Or use **Cloud Build** (no local Docker required):

```bash
gcloud builds submit . --config=infra/gcp/cloudbuild.yaml --substitutions=_IMAGE="$IMAGE"
```

> **Note:** `.dockerignore` excludes `venv`, `dashboard/node_modules`, and `data/runs/**`. The full repo (including `agents/reporting_browser_use/`) is still large; keep images updated only when you change dependencies or code.

---

## Phase 3 — Secrets (Secret Manager)

Store sensitive values **never** in the image:

| Secret | Used for |
|--------|-----------|
| `ANTHROPIC_API_KEY` | Agents that call Claude |
| `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` | Slack Bolt bot (if you run it) |
| `BROWSER_USE_API_KEY` | Browser-use (Offers/Ads / Reporting app) |
| DoorDash / portal passwords | Prefer **not** hardcoding; UI already sends some credentials per request — still use **TLS** and **IAP** or VPN for the app |

Example:

```bash
echo -n "your-key" | gcloud secrets create anthropic-api-key --data-file=-
```

Grant the **Cloud Run service account** access:

```bash
export SA="YOUR_PROJECT_NUMBER-compute@developer.gserviceaccount.com"
gcloud secrets add-iam-policy-binding anthropic-api-key \
  --member="serviceAccount:$SA" \
  --role="roles/secretmanager.secretAccessor"
```

At deploy time, map secrets to env vars (see Phase 4).

---

## Phase 4 — Deploy API to Cloud Run

Minimal deploy (public HTTPS URL — **lock down** for production):

```bash
gcloud run deploy ralphai-api \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated \
  --memory=2Gi \
  --cpu=2 \
  --timeout=3600 \
  --set-env-vars="TODC_DATA_DIR=/tmp/ralphai-data,PYTHONPATH=/app" \
  --set-secrets="ANTHROPIC_API_KEY=anthropic-api-key:latest"
```

**Production hardening:**

- Remove `--allow-unauthenticated` and use **IAM** (“Require authentication”), **IAP** in front of a load balancer, or **VPC** + internal ingress.
- Increase **memory/CPU** for large pandas / report jobs.
- Set **`TODC_DATA_DIR`** to a mounted **GCS FUSE** path or sync bucket ↔ disk on startup (custom entrypoint) so operator data survives restarts.

**Persist `data/` on GCS (conceptual):**

- Create a bucket `gs://YOUR_PROJECT-ralphai-data`.
- Use **Cloud Storage FUSE** in a **GCE** deployment, or a startup script that `gsutil rsync`s to `/app/data` before uvicorn starts.

---

## Phase 5 — Dashboard (same origin as `/api`)

The dashboard uses **relative** URLs such as `fetch("/api/runs/...")`. Browsers must see **the same host** for the SPA and `/api`, **unless** you change the frontend to use `import.meta.env.VITE_API_BASE_URL` and enable **CORS** on FastAPI.

### 5a — Firebase Hosting (recommended with Cloud Run)

1. `npm ci && npm run build` inside `dashboard/`.
2. Initialize Firebase in the repo (`firebase init hosting`).
3. In `firebase.json`, add **rewrites** so `/api/**` goes to your **Cloud Run** URL (Firebase “Cloud Run” integration) or use an **HTTPS LB** URL map.

Result: team opens `https://your-app.web.app`, static files load, `/api/*` hits Cloud Run.

### 5b — nginx on a VM (Option A)

Example server block (conceptual):

- `root` → `dashboard/dist`
- `location /api/` → `proxy_pass http://127.0.0.1:8080;`

Build the SPA:

```bash
cd dashboard
npm ci
npm run build
# Deploy `dist/` to the VM or bucket behind CDN
```

---

## Phase 6 — Custom domain + TLS for your team

1. **Cloud Run:** Add **domain mapping** (or put **External HTTPS Load Balancer** in front with managed certificate).
2. **Firebase Hosting:** Connect custom domain in Firebase console; follow DNS TXT verification.
3. **VM:** Use **Caddy** or **Certbot** with Let’s Encrypt.

---

## Phase 7 — Team access (who can open the app)

| Approach | Best for |
|----------|-----------|
| **Cloud Run + IAM** (“invoker” role) | Google accounts in your org only |
| **IAP** on HTTPS LB | Same, plus audit and SSO |
| **VPN + internal LB** | Strict network perimeter |
| **Firebase Auth** (not in repo today) | Would require frontend + API changes |

Start with **IAP** or **Run IAM** before exposing sensitive marketing data.

---

## Phase 8 — Slack bot (optional)

`run.sh` starts `slack_bot` when `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` are set. On GCP you typically run this as:

- A second **Cloud Run** service (always-on **min instances = 1**), or
- A **VM** process under **systemd**, or
- **Cloud Run Jobs** if you move to a pull model (would need code changes).

Slack must reach a **public HTTPS URL** for Events/Slash commands — configure **Slack app** Request URLs to your **API** or bot service.

---

## Operational checklist

- [ ] **Billing alerts** on the GCP project.
- [ ] **Backups** for `data/operators/` and `data/runs/` (GCS versioning or scheduled export).
- [ ] **Log sinks** to Cloud Logging; optional Error Reporting.
- [ ] **Uptime check** on `/api/health`.
- [ ] Document **`TODC_DATA_DIR`** and **`ACCOUNT_INFORMATION_CSV`** for operators (see `.env.example`).

---

## Important limitations

### Browser automation (Offers, Ads, Reporting `main.py`)

DoorDash flows use **browser-use** and often **Chrome**. **Cloud Run’s default** container is a poor fit (no Chrome, no display, cold starts, short timeouts unless raised). For reliable **Offers/Ads**:

- Run those endpoints on a **VM** with Chrome installed, **or**
- Use a **remote browser** (e.g. **Browserless**, or your existing **CDP** pattern in `LOCAL_BROWSER_CDP_URL` from `agents/reporting_browser_use`) and document env vars in Secret Manager.

### Long requests

Campaign review, MarketingReco, and browser runs can exceed **default** proxy timeouts. Set **Cloud Run timeout** (up to **60 minutes** on request), **LB timeout**, and **Firebase** limits accordingly.

### CORS

If you ever host the SPA on a **different origin** than the API, you must add **FastAPI CORSMiddleware** for that origin or use only server-side rewrites.

---

## Quick reference commands

```bash
# Logs
gcloud run services logs read ralphai-api --region="$REGION"

# New revision with updated image
gcloud run deploy ralphai-api --image="$IMAGE" --region="$REGION"

# Health
curl -sS "$(gcloud run services describe ralphai-api --region="$REGION" --format='value(status.url)')/api/health"
```

---

## Related files in this repo

| File | Purpose |
|------|---------|
| `infra/gcp/Dockerfile.api` | Production API container |
| `infra/gcp/cloudbuild.yaml` | Cloud Build — build/push with non-root Dockerfile path |
| `.dockerignore` | Smaller, safer image context |
| `.env.example` | Environment variable reference |
| `run.sh` | Local dev: API + Vite + optional Slack |

For a **VM-oriented** install, see `agents/reporting_browser_use/GCP_DEPLOYMENT_GUIDE.md` and `agents/reporting_browser_use/deploy/VM_SETUP_MANUAL.md`.

---

## Support checklist if something fails

1. **Cloud Run logs** — import errors, missing `PYTHONPATH`, missing `agents/reporting_browser_use` (override with `MARKETINGRECO_REPORTING_ROOT` if needed).
2. **`/api/health`** — returns `{"ok": true}`.
3. **Dashboard** — 404 on `/api/*` means **rewrite/proxy** not configured (same-origin issue).
4. **500 on long jobs** — timeout / memory; check **Cloud Run** metrics.
5. **Offers/Ads 500** — almost always **browser** / **API keys** / **Chrome**; move to **VM** or **remote CDP**.

This should be enough for your team to get a **first production cut** on GCP; tighten **auth**, **storage**, and **browser** placement before wide rollout.
