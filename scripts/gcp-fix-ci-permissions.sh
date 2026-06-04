#!/usr/bin/env bash
# Fix GitHub Actions / deploy SA "forbidden from accessing bucket *_cloudbuild"
# and missing serviceusage.services.use. Safe to re-run.
#
# Usage:
#   export GCP_PROJECT_ID=todc-marketing
#   ./scripts/gcp-fix-ci-permissions.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GCP_PROJECT_ID="${GCP_PROJECT_ID:-${GCP_PROJECT:-todc-marketing}}"
DEPLOY_SA_NAME="${DEPLOY_SA_NAME:-ralphai-github-deploy}"
DEPLOY_SA_EMAIL="${DEPLOY_SA_NAME}@${GCP_PROJECT_ID}.iam.gserviceaccount.com"

c_green='\033[1;32m'; c_blue='\033[1;34m'; c_off='\033[0m'
step() { echo -e "\n${c_blue}▸ $*${c_off}"; }
ok()   { echo -e "${c_green}✓ $*${c_off}"; }

command -v gcloud >/dev/null || { echo "Install gcloud first"; exit 1; }
gcloud config set project "$GCP_PROJECT_ID" >/dev/null

PROJECT_NUMBER="$(gcloud projects describe "$GCP_PROJECT_ID" --format='value(projectNumber)')"
CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

step "Enable APIs (Cloud Build, Storage, Service Usage)"
gcloud services enable \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  serviceusage.googleapis.com \
  artifactregistry.googleapis.com \
  run.googleapis.com \
  --project="$GCP_PROJECT_ID" \
  --quiet
ok "APIs enabled"

step "Project IAM for ${DEPLOY_SA_EMAIL}"
for ROLE in \
  roles/serviceusage.serviceUsageConsumer \
  roles/cloudbuild.builds.editor \
  roles/cloudbuild.builds.builder \
  roles/storage.admin \
  roles/storage.objectAdmin \
  roles/artifactregistry.admin \
  roles/run.admin \
  roles/iam.serviceAccountUser \
  roles/secretmanager.secretAccessor; do
  gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
    --member="serviceAccount:${DEPLOY_SA_EMAIL}" \
    --role="$ROLE" \
    --condition=None \
    --quiet >/dev/null 2>&1 || true
done
ok "Project roles updated"

step "Allow deploy SA to use Cloud Build service account"
gcloud iam service-accounts add-iam-policy-binding "$CB_SA" \
  --project="$GCP_PROJECT_ID" \
  --member="serviceAccount:${DEPLOY_SA_EMAIL}" \
  --role="roles/iam.serviceAccountUser" \
  --quiet >/dev/null 2>&1 || true
ok "iam.serviceAccountUser on ${CB_SA}"

step "Cloud Build default SA (image push + Run deploy)"
for ROLE in roles/artifactregistry.writer roles/run.admin roles/storage.admin; do
  gcloud projects add-iam-policy-binding "$GCP_PROJECT_ID" \
    --member="serviceAccount:${CB_SA}" \
    --role="$ROLE" \
    --quiet >/dev/null 2>&1 || true
done
ok "Cloud Build SA roles updated"

step "Cloud Build staging bucket IAM"
if command -v gsutil >/dev/null 2>&1; then
  for BUCKET in "${GCP_PROJECT_ID}_cloudbuild" "gs://${GCP_PROJECT_ID}_cloudbuild"; do
    BUCKET="${BUCKET#gs://}"
    if gsutil ls -b "gs://${BUCKET}" >/dev/null 2>&1; then
      gsutil iam ch "serviceAccount:${DEPLOY_SA_EMAIL}:roles/storage.objectAdmin" "gs://${BUCKET}" 2>/dev/null \
        || gsutil iam ch "serviceAccount:${DEPLOY_SA_EMAIL}:objectAdmin" "gs://${BUCKET}" 2>/dev/null \
        || true
      ok "Bucket gs://${BUCKET}"
    fi
  done
  LEGACY_BUCKET="${PROJECT_NUMBER}.cloudbuild-logs.googleusercontent.com"
  if gsutil ls -b "gs://${LEGACY_BUCKET}" >/dev/null 2>&1; then
    gsutil iam ch "serviceAccount:${DEPLOY_SA_EMAIL}:objectAdmin" "gs://${LEGACY_BUCKET}" 2>/dev/null || true
    ok "Bucket gs://${LEGACY_BUCKET}"
  fi
else
  echo "  (gsutil not found — project-level storage.admin should still cover buckets)"
fi

echo
ok "Done. Re-run GitHub Actions or: ./deploy.sh --deploy-only"
