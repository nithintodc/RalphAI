#!/usr/bin/env bash
# One-time GCP setup for local laptop deploy: RalphAI on Cloud Run.
#
# Usage:
#   export GCP_PROJECT_ID=your-project-id
#   export GCP_REGION=us-central1          # optional
#   ./scripts/gcp-bootstrap.sh
#
# Then deploy from your machine: ./deploy.sh --deploy-only
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GCP_PROJECT_ID="${GCP_PROJECT_ID:-todc-marketing}"
GCP_REGION="${GCP_REGION:-us-central1}"
# Reuses existing Cloud Run service (replaces prior image on each deploy).
SERVICE_NAME="${SERVICE_NAME:-todc-reporting-app}"
AR_REPOSITORY="${AR_REPOSITORY:-ralphai}"
SECRET_SA="${SECRET_SA:-todc-export-sa-json}"

c_blue='\033[1;34m'; c_green='\033[1;32m'; c_yellow='\033[1;33m'; c_red='\033[1;31m'; c_off='\033[0m'
step() { echo -e "\n${c_blue}▸ $*${c_off}"; }
ok()   { echo -e "${c_green}✓ $*${c_off}"; }
warn() { echo -e "${c_yellow}! $*${c_off}"; }
die()  { echo -e "${c_red}✗ $*${c_off}" >&2; exit 1; }

[[ -n "$GCP_PROJECT_ID" ]] || die "Set GCP_PROJECT_ID (e.g. export GCP_PROJECT_ID=todc-marketing)"
command -v gcloud >/dev/null || die "Install Google Cloud SDK: https://cloud.google.com/sdk"
gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . \
  || die "Run: gcloud auth login"

step "Project ${GCP_PROJECT_ID} · region ${GCP_REGION}"
gcloud config set project "$GCP_PROJECT_ID" >/dev/null

step "Enable APIs"
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  secretmanager.googleapis.com \
  --project="$GCP_PROJECT_ID" \
  --quiet
ok "APIs enabled"

step "Artifact Registry repository (${AR_REPOSITORY})"
if ! gcloud artifacts repositories describe "$AR_REPOSITORY" \
  --location="$GCP_REGION" --project="$GCP_PROJECT_ID" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$AR_REPOSITORY" \
    --repository-format=docker \
    --location="$GCP_REGION" \
    --project="$GCP_PROJECT_ID" \
    --description="RalphAI API images"
  ok "Created ${AR_REPOSITORY}"
else
  ok "Repository ${AR_REPOSITORY} already exists"
fi

PROJECT_NUMBER="$(gcloud projects describe "$GCP_PROJECT_ID" --format='value(projectNumber)')"

step "Secret Manager (create if missing)"
ensure_secret() {
  local name="$1"
  gcloud secrets describe "$name" --project="$GCP_PROJECT_ID" >/dev/null 2>&1 \
    || gcloud secrets create "$name" --replication-policy=automatic --project="$GCP_PROJECT_ID" --quiet
}

ensure_secret "ANTHROPIC_API_KEY"
ensure_secret "AIRTABLE_PAT"
ensure_secret "$SECRET_SA"
ensure_secret "SLACK_BOT_TOKEN"
ensure_secret "SLACK_SIGNING_SECRET"
ok "Secret resources created (add values below if empty)"

RUNTIME_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
for s in ANTHROPIC_API_KEY AIRTABLE_PAT "$SECRET_SA" SLACK_BOT_TOKEN SLACK_SIGNING_SECRET; do
  gcloud secrets add-iam-policy-binding "$s" \
    --project="$GCP_PROJECT_ID" \
    --member="serviceAccount:${RUNTIME_SA}" \
    --role="roles/secretmanager.secretAccessor" \
    --quiet >/dev/null 2>&1 || true
done
ok "Cloud Run runtime SA can read secrets"

add_secret_version() {
  local name="$1"
  local value="$2"
  [[ -n "$value" ]] || return 0
  printf '%s' "$value" | gcloud secrets versions add "$name" --data-file=- --project="$GCP_PROJECT_ID" --quiet
  ok "Secret ${name} updated"
}

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  set -a; source .env; set +a
  warn "Loading values from .env into Secret Manager"
fi

SA_JSON="${SA_JSON:-}"
if [[ -z "$SA_JSON" ]]; then
  SA_JSON="$(ls agents/the_super_app/streamlit_app/todc-marketing-*.json 2>/dev/null | head -1 || true)"
fi
if [[ -n "$SA_JSON" && -f "$SA_JSON" ]]; then
  gcloud secrets versions add "$SECRET_SA" --data-file="$SA_JSON" --project="$GCP_PROJECT_ID" --quiet
  ok "Secret ${SECRET_SA} ← $(basename "$SA_JSON")"
else
  warn "No todc-marketing-*.json found — add ${SECRET_SA} manually for Google Drive export"
fi

add_secret_version "AIRTABLE_PAT" "${AIRTABLE_PAT:-}"
add_secret_version "ANTHROPIC_API_KEY" "${ANTHROPIC_API_KEY:-}"
add_secret_version "SLACK_BOT_TOKEN" "${SLACK_BOT_TOKEN:-}"
add_secret_version "SLACK_SIGNING_SECRET" "${SLACK_SIGNING_SECRET:-}"

echo
echo -e "${c_green}════════════════════════════════════════════════════════════${c_off}"
echo -e "${c_green}  GCP bootstrap complete${c_off}"
echo -e "${c_green}════════════════════════════════════════════════════════════${c_off}"
echo
echo "  Fill any empty secrets in GCP Console → Secret Manager, e.g.:"
echo "    echo -n 'pat...' | gcloud secrets versions add AIRTABLE_PAT --data-file=-"
echo
echo "  Deploy from your laptop:"
echo "    gcloud auth login"
echo "    ./deploy.sh --deploy-only"
echo
echo "  Service name: ${SERVICE_NAME}"
echo "  Image: ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPOSITORY}/${SERVICE_NAME}:<tag>"
