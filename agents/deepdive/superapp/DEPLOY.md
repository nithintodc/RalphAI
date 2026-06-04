# Deploying TheSuperApp

Two services, one ecosystem (GCP):

| Part | Where | Why |
|------|-------|-----|
| **Backend** `streamlit_app/export_api.py` | **GCP Cloud Run** | Persistent HTTP server that holds the Google service account + Airtable token and pushes to Drive/Sheets/Docs. Containerized, scales to zero. |
| **Frontend** `app/` (Vite/React SPA) | **Firebase Hosting** | Static SPA on a global CDN. Built with the live Cloud Run URL injected. |

> Netlify/Vercel were ruled out for the backend: it's a credentialed long-running server, not a static site or stateless function.

## One-time setup

```bash
# 1. Tools
brew install --cask google-cloud-sdk     # or https://cloud.google.com/sdk
npm i -g firebase-tools

# 2. Auth
gcloud auth login
firebase login

# 3. Credentials (local, gitignored)
#  - streamlit_app/todc-marketing-*.json   ← Google service-account key
#  - .env                                  ← AIRTABLE_PAT, AIRTABLE_BASE_ID, AIRTABLE_TABLE_ID
```

The service account must have access to the `Data-Analysis-Uploads` Shared Drive.

## Deploy

```bash
./deploy.sh <GCP_PROJECT_ID>          # backend (Cloud Run) + frontend (Firebase)
./deploy.sh <GCP_PROJECT_ID> --backend-only
./deploy.sh <GCP_PROJECT_ID> --frontend-only   # rebuild SPA against existing API
```

What it does:
1. Enables APIs (Run, Cloud Build, Artifact Registry, Secret Manager).
2. Pushes the service-account JSON → Secret Manager (`todc-export-sa-json`) and
   `AIRTABLE_PAT` → `todc-airtable-pat`; grants the Cloud Run runtime SA access.
3. `gcloud run deploy todc-export-api --source streamlit_app` (uses the Dockerfile).
4. Builds the SPA with `VITE_GOOGLE_SHEETS_EXPORT_URL=<run-url>/export` and
   `VITE_EXPORT_API_BASE=<run-url>` baked in (Export button + Store Map work in prod).
5. `firebase deploy --only hosting`.

Overridable env: `GCP_REGION` (default `us-central1`), `SERVICE_NAME`,
`GOOGLE_SHARED_DRIVE_NAME`, `FIREBASE_PROJECT`, `SA_JSON`.

## Push to git

`$HOME` is itself a git repo — so `git.sh` creates/uses a **dedicated** repo at
TheSuperApp and refuses to touch the home repo. It also scans staged files for
secrets before committing.

```bash
./git.sh "your message"                                   # commit (+ push if origin set)
./git.sh "first commit" git@github.com:you/thesuperapp.git # set origin & push
```

## Local dev (unchanged)

```bash
python3 streamlit_app/export_api.py   # API on :8765
cd app && npm run dev                  # SPA on :5173
```
