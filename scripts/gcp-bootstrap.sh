#!/usr/bin/env bash
# One-time GCP setup for Path A: RalphAI on Cloud Run + GitHub Actions CI.
#
# Usage:
#   export GCP_PROJECT_ID=your-project-id
#   export GCP_REGION=us-central1          # optional
#   ./scripts/gcp-bootstrap.sh
#
# Then add the printed GitHub secrets and push to main.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GCP_PROJECT_ID="${GCP_PROJECT_ID:-todc-marketing}"
GCP_REGION="${GCP_REGION:-us-central1}"
# Reuses existing Cloud Run service (replaces prior image on each deploy).
SERVICE_NAME="${SERVICE_NAME:-todc-reporting-app}"
AR_REPOSITORY="${AR_REPOSITORY:-ralphai}"
DEPLOY_SA_NAME="${DEPLOY_SA_NAME:-ralphai-github-deploy}"
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

step "Deploy service account (${DEPLOY_SA_NAME})"
DEPLOY_SA_EMAIL="${DEPLOY_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$DEPLOY_SA_EMAIL" --project="$GCP_PROJECT_ID" >/dev/null 2>&1; then
  gcloud iam service-accounts create "$DEPLOY_SA_NAME" \
    --display-name="RalphAI GitHub Actions deploy" \
    --project="$GCP_PROJECT_ID"
  ok "Created ${DEPLOY_SA_EMAIL}"
else
  ok "Service account exists"
fi

for ROLE in \
  roles/run.admin \
  roles/artifactregistry.admin \
  roles/cloudbuild.builds.editor \
  roles/iam.serviceAccountUser \
  roles/storage.admin \
  roles/secretmanager.admin; do
  gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
    --member="serviceAccount:${DEPLOY_SA_EMAIL}" \
    --role="$ROLE" \
    --quiet >/dev/null 2>&1 || true
done
ok "IAM roles bound to deploy SA"

# Cloud Build default SA can push images
PROJECT_NUMBER="$(gcloud projects describe "$GCP_PROJECT_ID" --format='value(projectNumber)')"
CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:${CB_SA}" \
  --role="roles/artifactregistry.writer" \
  --quiet >/dev/null 2>&1 || true
gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
  --member="serviceAccount:${CB_SA}" \
  --role="roles/run.admin" \
  --quiet >/dev/null 2>&1 || true
ok "Cloud Build SA can push images and deploy Run"

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

KEY_FILE="${ROOT}/.gcp/${DEPLOY_SA_NAME}-key.json"
mkdir -p "${ROOT}/.gcp"
step "Deploy SA key for GitHub (saved locally, gitignored)"
gcloud iam service-accounts keys create "$KEY_FILE" \
  --iam-account="$DEPLOY_SA_EMAIL" \
  --project="$GCP_PROJECT_ID"
ok "Key written to ${KEY_FILE}"

echo
echo -e "${c_green}════════════════════════════════════════════════════════════${c_off}"
echo -e "${c_green}  GCP bootstrap complete — add these GitHub secrets${c_off}"
echo -e "${c_green}════════════════════════════════════════════════════════════${c_off}"
echo
echo "  Repo → Settings → Secrets and variables → Actions → New repository secret"
echo
echo "  GCP_PROJECT_ID     = ${GCP_PROJECT_ID}"
echo "  GCP_REGION         = ${GCP_REGION}"
echo "  GCP_SA_KEY         = entire contents of:"
echo "                       ${KEY_FILE}"
echo
echo "  Optional repository variables (Settings → Variables):"
echo "  AIRTABLE_BASE_ID, AIRTABLE_TABLE_ID, CORS_ORIGINS, GOOGLE_SHARED_DRIVE_NAME"
echo
echo "  Fill any empty secrets in GCP Console → Secret Manager, e.g.:"
echo "    echo -n 'pat...' | gcloud secrets versions add AIRTABLE_PAT --data-file=-"
echo
echo "  Then push to main — workflow: .github/workflows/deploy-ralphai.yml"
echo "  Service name: ${SERVICE_NAME}"
echo "  Image: ${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPOSITORY}/${SERVICE_NAME}:<git-sha>"
echo
warn "Do not commit ${KEY_FILE} — it is listed in .gitignore"
