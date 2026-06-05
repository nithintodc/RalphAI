#!/usr/bin/env bash
#
# deploy.sh — Path A: RalphAI → Cloud Run (todc-reporting-app)
#
# Replaces the old app on your existing Cloud Run service in todc-marketing.
# Dashboard + API + Super App ship in one container (infra/gcp/Dockerfile.api).
#
# Usage:
#   ./deploy.sh                    # full: bootstrap (if needed) + build + deploy
#   ./deploy.sh todc-marketing     # same, explicit project
#   ./deploy.sh --bootstrap-only   # one-time GCP APIs, secrets, GitHub deploy key
#   ./deploy.sh --deploy-only      # Cloud Build + Cloud Run (skip bootstrap)
#   ./deploy.sh --github-secrets   # print / optionally set GitHub Actions secrets (needs gh)
#   ./deploy.sh --prepare          # local npm/py build + tests only
#   ./deploy.sh --fix-ci-permissions  # fix Cloud Build bucket / serviceusage errors
#   ./deploy.sh --legacy-superapp  # old path: todc-export-api + Firebase Hosting
#
# Env (optional):
#   GCP_PROJECT_ID=todc-marketing  GCP_REGION=us-central1
#   SERVICE_NAME=todc-reporting-app
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# Path A defaults (existing Cloud Run service in Console)
GCP_PROJECT_ID="${GCP_PROJECT_ID:-${GCP_PROJECT:-todc-marketing}}"
GCP_REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-todc-reporting-app}"
AR_REPOSITORY="${AR_REPOSITORY:-ralphai}"
GOOGLE_SHARED_DRIVE_NAME="${GOOGLE_SHARED_DRIVE_NAME:-Data-Analysis-Uploads}"
DEPLOY_KEY_FILE="${ROOT}/.gcp/ralphai-github-deploy-key.json"

MODE="full"
SKIP_BOOTSTRAP=0
SET_GITHUB_SECRETS=0

c_blue='\033[1;34m'; c_green='\033[1;32m'; c_yellow='\033[1;33m'; c_red='\033[1;31m'; c_off='\033[0m'
step() { echo -e "\n${c_blue}▸ $*${c_off}"; }
ok()   { echo -e "${c_green}✓ $*${c_off}"; }
warn() { echo -e "${c_yellow}! $*${c_off}"; }
die()  { echo -e "${c_red}✗ $*${c_off}" >&2; exit 1; }

usage() {
  sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
  exit 0
}

for arg in "$@"; do
  case "$arg" in
    -h|--help) usage ;;
    --bootstrap-only)     MODE="bootstrap" ;;
    --deploy-only)      MODE="deploy"; SKIP_BOOTSTRAP=1 ;;
    --github-secrets)     MODE="github" ;;
    --prepare)            MODE="prepare" ;;
    --legacy-superapp)    MODE="legacy" ;;
    --skip-bootstrap)     SKIP_BOOTSTRAP=1 ;;
    --set-github-secrets) SET_GITHUB_SECRETS=1 ;;
    --fix-ci-permissions) MODE="fix-ci" ;;
    --*) die "Unknown flag: $arg (try --help)" ;;
    *)
      if [[ -z "${GCP_PROJECT_ID_SET:-}" ]]; then
        GCP_PROJECT_ID="$arg"
        GCP_PROJECT_ID_SET=1
      fi
      ;;
  esac
done

preflight_gcloud() {
  command -v gcloud >/dev/null || die "Install Google Cloud SDK: https://cloud.google.com/sdk"
  gcloud auth list --filter=status:ACTIVE --format='value(account)' | grep -q . \
    || die "Run: gcloud auth login"
  export GCP_PROJECT_ID GCP_REGION SERVICE_NAME
  gcloud config set project "$GCP_PROJECT_ID" >/dev/null 2>&1
  ok "gcloud · project=$GCP_PROJECT_ID · region=$GCP_REGION · service=$SERVICE_NAME"
}

load_env() {
  if [[ -f .env ]]; then
    set -a
    # shellcheck disable=SC1091
    source .env
    set +a
    ok "Loaded .env"
  fi
}

run_bootstrap() {
  step "GCP bootstrap (APIs, Artifact Registry, secrets, GitHub deploy key)"
  GCP_PROJECT_ID="$GCP_PROJECT_ID" GCP_REGION="$GCP_REGION" SERVICE_NAME="$SERVICE_NAME" \
    "$ROOT/scripts/gcp-bootstrap.sh"
}

print_github_secrets_help() {
  echo
  echo -e "${c_green}════════════════════════════════════════════════════════════${c_off}"
  echo -e "${c_green}  GitHub Actions secrets (one-time)${c_off}"
  echo -e "${c_green}════════════════════════════════════════════════════════════${c_off}"
  echo
  echo "  https://github.com/YOUR_ORG/RalphAI/settings/secrets/actions"
  echo
  echo "  GCP_PROJECT_ID  =  ${GCP_PROJECT_ID}"
  echo "  GCP_REGION      =  ${GCP_REGION}"
  echo "  GCP_SA_KEY      =  entire file:"
  echo "                     ${DEPLOY_KEY_FILE}"
  echo
  echo "  Copy key to clipboard (macOS):"
  echo "    cat ${DEPLOY_KEY_FILE} | pbcopy"
  echo
  echo "  After secrets are set, every push to main deploys via:"
  echo "    .github/workflows/deploy-ralphai.yml"
  echo
  if [[ -f "$DEPLOY_KEY_FILE" ]]; then
    warn "Never commit ${DEPLOY_KEY_FILE}"
  else
    warn "Run ./deploy.sh --bootstrap-only first to create ${DEPLOY_KEY_FILE}"
  fi
}

set_github_secrets_with_gh() {
  command -v gh >/dev/null || die "Install GitHub CLI: brew install gh && gh auth login"
  gh auth status >/dev/null 2>&1 || die "Run: gh auth login"
  [[ -f "$DEPLOY_KEY_FILE" ]] || die "Missing ${DEPLOY_KEY_FILE} — run --bootstrap-only first"

  step "Setting GitHub Actions secrets via gh CLI"
  gh secret set GCP_PROJECT_ID --body "$GCP_PROJECT_ID"
  gh secret set GCP_REGION --body "$GCP_REGION"
  gh secret set GCP_SA_KEY < "$DEPLOY_KEY_FILE"
  ok "GitHub secrets set (GCP_PROJECT_ID, GCP_REGION, GCP_SA_KEY)"
}

build_cloud_run_secret_flags() {
  SECRET_FLAGS=""
  add_secret() {
    local env_name="$1"
    local secret_name="$2"
    if ! gcloud secrets describe "${secret_name}" --project="${GCP_PROJECT_ID}" >/dev/null 2>&1; then
      warn "Skipping secret ${secret_name} (not in Secret Manager)"
      return
    fi
    if ! gcloud secrets versions list "${secret_name}" \
      --project="${GCP_PROJECT_ID}" --limit=1 --format='value(name)' \
      | grep -q .; then
      warn "Skipping secret ${secret_name} (no enabled version)"
      return
    fi
    if [[ -n "${SECRET_FLAGS}" ]]; then SECRET_FLAGS+=","; fi
    SECRET_FLAGS+="${env_name}=${secret_name}:latest"
  }
  add_secret "ANTHROPIC_API_KEY" "ANTHROPIC_API_KEY"
  add_secret "AIRTABLE_PAT" "AIRTABLE_PAT"
  add_secret "GCP_SERVICE_ACCOUNT_JSON" "todc-export-sa-json"
  add_secret "SLACK_BOT_TOKEN" "SLACK_BOT_TOKEN"
  add_secret "SLACK_SIGNING_SECRET" "SLACK_SIGNING_SECRET"
}

deploy_cloud_run() {
  preflight_gcloud
  load_env
  build_cloud_run_secret_flags

  TAG="${IMAGE_TAG:-$(git rev-parse --short HEAD 2>/dev/null || echo "manual-$(date +%Y%m%d%H%M)")}"
  IMAGE="${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPOSITORY}/${SERVICE_NAME}:${TAG}"

  if [[ "${SKIP_BUILD:-0}" != "1" ]]; then
    step "Cloud Build → ${IMAGE}"
    gcloud auth configure-docker "${GCP_REGION}-docker.pkg.dev" --quiet
    gcloud builds submit . \
      --config=infra/gcp/cloudbuild.yaml \
      --substitutions=_IMAGE="${IMAGE}" \
      --project="${GCP_PROJECT_ID}" \
      --quiet
    ok "Image built and pushed"
  else
    ok "Skipping build — using existing image ${IMAGE}"
  fi

  # Path A: UI + API same host — gcloud --env-vars-file requires YAML (not KEY=VALUE).
  ENV_FILE="$(mktemp)"
  {
    echo "LOG_LEVEL: INFO"
    echo "GOOGLE_SHARED_DRIVE_NAME: ${GOOGLE_SHARED_DRIVE_NAME}"
    [[ -n "${AIRTABLE_BASE_ID:-}" ]]  && echo "AIRTABLE_BASE_ID: ${AIRTABLE_BASE_ID}"
    [[ -n "${AIRTABLE_TABLE_ID:-}" ]] && echo "AIRTABLE_TABLE_ID: ${AIRTABLE_TABLE_ID}"
    if [[ -n "${CLOUD_RUN_CORS_ORIGINS:-}" ]]; then
      echo "CORS_ORIGINS: ${CLOUD_RUN_CORS_ORIGINS}"
    fi
  } >"$ENV_FILE"

  step "Cloud Run deploy → ${SERVICE_NAME}"
  DEPLOY_ARGS=(
    run deploy "${SERVICE_NAME}"
    --image="${IMAGE}"
    --region="${GCP_REGION}"
    --platform=managed
    --allow-unauthenticated
    --memory=2Gi
    --cpu=2
    --timeout=3600
    --max-instances=5
    --min-instances=0
    --project="${GCP_PROJECT_ID}"
    --env-vars-file="${ENV_FILE}"
    --quiet
  )
  if [[ -n "${SECRET_FLAGS:-}" ]]; then
    DEPLOY_ARGS+=(--update-secrets="${SECRET_FLAGS}")
  fi
  # Drop secrets that have no enabled version (would block revision startup).
  REMOVE_SECRETS=""
  for stale in ANTHROPIC_API_KEY SLACK_BOT_TOKEN SLACK_SIGNING_SECRET; do
    if gcloud run services describe "${SERVICE_NAME}" \
      --region="${GCP_REGION}" --project="${GCP_PROJECT_ID}" \
      --format='yaml(spec.template.spec.containers[0].env)' 2>/dev/null \
      | grep -q "name: ${stale}"; then
      [[ -n "${REMOVE_SECRETS}" ]] && REMOVE_SECRETS+=","
      REMOVE_SECRETS+="${stale}"
    fi
  done
  if [[ -n "${REMOVE_SECRETS}" ]]; then
    DEPLOY_ARGS+=(--remove-secrets="${REMOVE_SECRETS}")
  fi
  gcloud "${DEPLOY_ARGS[@]}"
  rm -f "$ENV_FILE"

  URL="$(gcloud run services describe "${SERVICE_NAME}" \
    --region="${GCP_REGION}" \
    --project="${GCP_PROJECT_ID}" \
    --format='value(status.url)')"
  echo
  ok "RalphAI is live: ${URL}"
  echo "  Dashboard:     ${URL}/"
  echo "  Super App:     ${URL}/agents/the-super-app"
  echo "  Health Check:  ${URL}/agents/health-check"
}

run_prepare() {
  step "Local prepare (build + tests)"
  "$ROOT/scripts/prepare-deploy.sh"
}

# ─── Legacy: Super App export API + Firebase (Path B) ───────────────────────
deploy_legacy_superapp() {
  GCP_PROJECT="${GCP_PROJECT_ID}"
  SERVICE_NAME_LEGACY="${SERVICE_NAME_LEGACY:-todc-export-api}"
  FIREBASE_PROJECT="${FIREBASE_PROJECT:-$GCP_PROJECT}"
  SECRET_SA="${SECRET_SA:-todc-export-sa-json}"
  SECRET_AIRTABLE="${SECRET_AIRTABLE:-todc-airtable-pat}"
  SA_JSON="${SA_JSON:-}"
  if [[ -z "$SA_JSON" ]]; then
    SA_JSON="$(ls agents/the_super_app/streamlit_app/todc-marketing-*.json 2>/dev/null | head -1 || true)"
  fi
  command -v firebase >/dev/null || die "firebase-tools required for --legacy-superapp"
  preflight_gcloud
  load_env
  [[ -n "$SA_JSON" && -f "$SA_JSON" ]] || die "Set SA_JSON=path to todc-marketing-*.json"

  gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
    artifactregistry.googleapis.com secretmanager.googleapis.com --quiet

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
  local secret_flags="GCP_SERVICE_ACCOUNT_JSON=${SECRET_SA}:latest"
  if [[ -n "${AIRTABLE_PAT:-}" ]]; then
    ensure_secret "$SECRET_AIRTABLE" val "$AIRTABLE_PAT"
    secret_flags="${secret_flags},AIRTABLE_PAT=${SECRET_AIRTABLE}:latest"
  fi
  local env_vars="GOOGLE_SHARED_DRIVE_NAME=${GOOGLE_SHARED_DRIVE_NAME}"
  [[ -n "${AIRTABLE_BASE_ID:-}" ]]  && env_vars="${env_vars},AIRTABLE_BASE_ID=${AIRTABLE_BASE_ID}"
  [[ -n "${AIRTABLE_TABLE_ID:-}" ]] && env_vars="${env_vars},AIRTABLE_TABLE_ID=${AIRTABLE_TABLE_ID}"

  step "Legacy deploy: Cloud Run ${SERVICE_NAME_LEGACY}"
  gcloud run deploy "$SERVICE_NAME_LEGACY" \
    --source agents/the_super_app/streamlit_app \
    --region "$GCP_REGION" \
    --platform managed \
    --allow-unauthenticated \
    --memory 512Mi --cpu 1 --timeout 120 --max-instances 5 \
    --set-env-vars "$env_vars" \
    --update-secrets "$secret_flags" \
    --quiet
  API_URL="$(gcloud run services describe "$SERVICE_NAME_LEGACY" --region "$GCP_REGION" --format='value(status.url)')"
  step "Legacy deploy: Firebase Hosting"
  ( cd agents/the_super_app/app
    [[ -d node_modules ]] || npm ci
    VITE_GOOGLE_SHEETS_EXPORT_URL="${API_URL}/export" \
    VITE_EXPORT_API_BASE="${API_URL}" \
      npm run build
  )
  ( cd agents/the_super_app && firebase deploy --only hosting --project "$FIREBASE_PROJECT" --non-interactive )
  ok "Legacy Super App: API ${API_URL} · Firebase hosting"
}

# ─── Main ────────────────────────────────────────────────────────────────────
case "$MODE" in
  bootstrap)
    preflight_gcloud
    load_env
    run_bootstrap
    print_github_secrets_help
    ;;
  deploy)
    deploy_cloud_run
    print_github_secrets_help
    ;;
  github)
    print_github_secrets_help
    [[ "$SET_GITHUB_SECRETS" == "1" ]] && set_github_secrets_with_gh
    ;;
  prepare)
    run_prepare
    ;;
  legacy)
    deploy_legacy_superapp
    ;;
  fix-ci)
    preflight_gcloud
    GCP_PROJECT_ID="$GCP_PROJECT_ID" "$ROOT/scripts/gcp-fix-ci-permissions.sh"
    ;;
  full)
    preflight_gcloud
    load_env
    if [[ "$SKIP_BOOTSTRAP" == "0" && ! -f "$DEPLOY_KEY_FILE" ]]; then
      warn "No ${DEPLOY_KEY_FILE} — running bootstrap first"
      run_bootstrap
    elif [[ "$SKIP_BOOTSTRAP" == "0" ]]; then
      ok "Bootstrap key exists — skipping (use --bootstrap-only to re-run)"
    fi
    deploy_cloud_run
    print_github_secrets_help
    if [[ "$SET_GITHUB_SECRETS" == "1" ]]; then
      set_github_secrets_with_gh || warn "Could not set GitHub secrets automatically"
    fi
    echo
    echo "  Optional: push to main for CI deploys"
    echo "    git push origin main"
    ;;
esac

echo
ok "Done (${MODE})"
