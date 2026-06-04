#!/usr/bin/env bash
#
# deploy.sh — Deploy RalphAI (TheSuperApp TODC analytics dashboard).
#
#   Backend  → GCP Cloud Run   (agents/the_super_app/streamlit_app, containerized)
#   Frontend → Firebase Hosting (agents/the_super_app/app, Vite static SPA)
#
# Usage:
#   ./deploy.sh <GCP_PROJECT_ID>            # full deploy (backend + frontend)
#   GCP_PROJECT=my-proj ./deploy.sh         # same, via env
#   ./deploy.sh <PROJECT> --backend-only
#   ./deploy.sh <PROJECT> --frontend-only
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

GCP_PROJECT="${GCP_PROJECT:-}"
MODE="full"
for arg in "$@"; do
  case "$arg" in
    --backend-only)  MODE="backend" ;;
    --frontend-only) MODE="frontend" ;;
    --*)             echo "Unknown flag: $arg" >&2; exit 1 ;;
    *)               GCP_PROJECT="$arg" ;;
  esac
done

GCP_REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-todc-export-api}"
GOOGLE_SHARED_DRIVE_NAME="${GOOGLE_SHARED_DRIVE_NAME:-Data-Analysis-Uploads}"
FIREBASE_PROJECT="${FIREBASE_PROJECT:-$GCP_PROJECT}"
SECRET_SA="${SECRET_SA:-todc-export-sa-json}"
SECRET_AIRTABLE="${SECRET_AIRTABLE:-todc-airtable-pat}"

SA_JSON="${SA_JSON:-}"
if [[ -z "$SA_JSON" ]]; then
  SA_JSON="$(ls agents/the_super_app/streamlit_app/todc-marketing-*.json 2>/dev/null | head -1 || true)"
fi

c_blue='\033[1;34m'; c_green='\033[1;32m'; c_yellow='\033[1;33m'; c_red='\033[1;31m'; c_off='\033[0m'
step() { echo -e "\n${c_blue}▸ $*${c_off}"; }
ok()   { echo -e "${c_green}✓ $*${c_off}"; }
warn() { echo -e "${c_yellow}! $*${c_off}"; }
die()  { echo -e "${c_red}✗ $*${c_off}" >&2; exit 1; }

step "Preflight checks"
[[ -n "$GCP_PROJECT" ]] || die "Set the GCP project: ./deploy.sh <PROJECT_ID>  (or GCP_PROJECT=…)"
command -v gcloud >/dev/null  || die "gcloud not found. Install the Google Cloud SDK."
command -v npm    >/dev/null  || die "npm not found. Install Node.js."
if [[ "$MODE" != "backend" ]]; then
  command -v firebase >/dev/null || die "firebase not found. Install firebase-tools."
fi
gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . \
  || die "gcloud is not authenticated. Run: gcloud auth login"
ok "Tooling present · project=$GCP_PROJECT region=$GCP_REGION mode=$MODE"

if [[ -f .env ]]; then set -a; . ./.env; set +a; ok "Loaded ./.env"; fi
gcloud config set project "$GCP_PROJECT" >/dev/null 2>&1

API_URL=""

deploy_backend() {
  step "Enabling required GCP APIs"
  gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
    artifactregistry.googleapis.com secretmanager.googleapis.com --quiet
  ok "APIs enabled"

  [[ -n "$SA_JSON" && -f "$SA_JSON" ]] \
    || die "Service-account JSON not found. Set SA_JSON=path"

  ensure_secret() {
    local name="$1" mode="$2" src="$3"
    gcloud secrets describe "$name" >/dev/null 2>&1 \
      || gcloud secrets create "$name" --replication-policy=automatic --quiet
    if [[ "$mode" == "file" ]]; then
      gcloud secrets versions add "$name" --data-file="$src" --quiet >/dev/null
    else
      printf '%s' "$src" | gcloud secrets versions add "$name" --data-file=- --quiet >/dev/null
    fi
  }
  ensure_secret "$SECRET_SA" file "$SA_JSON"
  ok "Secret $SECRET_SA ← $(basename "$SA_JSON")"

  local secret_flags="GCP_SERVICE_ACCOUNT_JSON=${SECRET_SA}:latest"
  if [[ -n "${AIRTABLE_PAT:-}" ]]; then
    ensure_secret "$SECRET_AIRTABLE" val "$AIRTABLE_PAT"
    secret_flags="${secret_flags},AIRTABLE_PAT=${SECRET_AIRTABLE}:latest"
    ok "Secret $SECRET_AIRTABLE ← AIRTABLE_PAT (from .env)"
  fi

  local proj_num runtime_sa
  proj_num="$(gcloud projects describe "$GCP_PROJECT" --format='value(projectNumber)')"
  runtime_sa="${proj_num}-compute@developer.gserviceaccount.com"
  for s in "$SECRET_SA" "$SECRET_AIRTABLE"; do
    gcloud secrets describe "$s" >/dev/null 2>&1 || continue
    gcloud secrets add-iam-policy-binding "$s" \
      --member="serviceAccount:${runtime_sa}" \
      --role="roles/secretmanager.secretAccessor" --quiet >/dev/null 2>&1 || true
  done

  local env_vars="GOOGLE_SHARED_DRIVE_NAME=${GOOGLE_SHARED_DRIVE_NAME}"
  [[ -n "${AIRTABLE_BASE_ID:-}" ]]  && env_vars="${env_vars},AIRTABLE_BASE_ID=${AIRTABLE_BASE_ID}"
  [[ -n "${AIRTABLE_TABLE_ID:-}" ]] && env_vars="${env_vars},AIRTABLE_TABLE_ID=${AIRTABLE_TABLE_ID}"

  step "Deploying backend to Cloud Run ($SERVICE_NAME)"
  gcloud run deploy "$SERVICE_NAME" \
    --source agents/the_super_app/streamlit_app \
    --region "$GCP_REGION" \
    --platform managed \
    --allow-unauthenticated \
    --memory 512Mi \
    --cpu 1 \
    --timeout 120 \
    --max-instances 5 \
    --set-env-vars "$env_vars" \
    --update-secrets "$secret_flags" \
    --quiet

  API_URL="$(gcloud run services describe "$SERVICE_NAME" --region "$GCP_REGION" --format='value(status.url)')"
  [[ -n "$API_URL" ]] || die "Could not read Cloud Run URL"
  ok "Backend live: $API_URL"
}

deploy_frontend() {
  if [[ -z "$API_URL" ]]; then
    API_URL="$(gcloud run services describe "$SERVICE_NAME" --region "$GCP_REGION" --format='value(status.url)' 2>/dev/null || true)"
    [[ -n "$API_URL" ]] || die "No Cloud Run service '$SERVICE_NAME' found."
    ok "Using backend: $API_URL"
  fi

  step "Building frontend (Vite)"
  ( cd agents/the_super_app/app
    [[ -d node_modules ]] || npm ci
    VITE_GOOGLE_SHEETS_EXPORT_URL="${API_URL}/export" \
    VITE_EXPORT_API_BASE="${API_URL}" \
      npm run build
  )
  ok "Built app/dist"

  step "Deploying frontend to Firebase Hosting ($FIREBASE_PROJECT)"
  # Assuming the firebase.json is in the RalphAI root or agents/the_super_app
  # We will execute from agents/the_super_app which has firebase.json (if applicable).
  # Otherwise we use the workspace level one.
  ( cd agents/the_super_app
    firebase deploy --only hosting --project "$FIREBASE_PROJECT" --non-interactive
  )
  ok "Frontend deployed"
}

case "$MODE" in
  backend)  deploy_backend ;;
  frontend) deploy_frontend ;;
  full)     deploy_backend; deploy_frontend ;;
esac

echo
ok "Deploy complete"
