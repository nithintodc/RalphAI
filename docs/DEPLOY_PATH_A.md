# Path A: Deploy RalphAI to Cloud Run

Deploys to **`todc-reporting-app`** in **`todc-marketing`** (`us-central1`).

Production URL: `https://todc-reporting-app-886692368169.us-central1.run.app`

---

## One command (recommended)

```bash
cd /path/to/RalphAI
gcloud auth login
./deploy.sh
```

That runs:

1. **Bootstrap** (first time only) — APIs, Artifact Registry, Secret Manager, `.gcp/ralphai-github-deploy-key.json`
2. **Cloud Build** — Docker image (dashboard + Super App + API)
3. **Cloud Run deploy** — replaces the old app on `todc-reporting-app`
4. **GitHub secrets reminder** — what to paste for CI

### Other commands

| Command | What it does |
|---------|----------------|
| `./deploy.sh --bootstrap-only` | One-time GCP + GitHub deploy key only |
| `./deploy.sh --deploy-only` | Build + deploy (skip bootstrap) |
| `./deploy.sh --github-secrets` | Show GitHub secret instructions |
| `./deploy.sh --set-github-secrets` | Same + auto-set secrets via `gh` CLI |
| `./deploy.sh --prepare` | Local build + tests only |
| `./deploy.sh --fix-ci-permissions` | Fix Cloud Build bucket / `serviceusage` errors |
| `./deploy.sh --help` | Full usage |

### GitHub CI (after bootstrap)

Add secrets (or run `./deploy.sh --set-github-secrets` if you use `gh`):

| Secret | Value |
|--------|--------|
| `GCP_PROJECT_ID` | `todc-marketing` |
| `GCP_REGION` | `us-central1` |
| `GCP_SA_KEY` | Contents of `.gcp/ralphai-github-deploy-key.json` |

Then:

```bash
git push origin main
```

Workflow: `.github/workflows/deploy-ralphai.yml`

---

## Prerequisites

- Google Cloud SDK (`gcloud`), billing on `todc-marketing`
- `.env` with `AIRTABLE_PAT` (bootstrap loads it into Secret Manager)
- `agents/the_super_app/streamlit_app/todc-marketing-*.json` for Drive export (optional)

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `gcloud auth login` | Required once per machine |
| `forbidden from accessing bucket *_cloudbuild` | Run `./deploy.sh --fix-ci-permissions`, re-run Actions |
| Permission denied on build | `./deploy.sh --fix-ci-permissions` or `--bootstrap-only` |
| Super App 503 | Re-run `./deploy.sh --deploy-only` |
| Rollback | Cloud Run → Revisions → previous revision |

See also: [README.md](../README.md) deployment section.
