# Multilogin profiles for RalphAI browser agents

DoorDash is already logged in inside Multilogin browser profiles. RalphAI starts the matching profile and attaches browser-use over CDP.

**Official API reference:** [Multilogin X API (Postman)](https://documenter.getpostman.com/view/28533318/2s946h9Cv9) — sign-in, workspaces, start/stop profile, automation ports. See also [Selenium automation example](https://multilogin.com/help/en_US/selenium-automation-example) and [starting a profile with Postman](https://multilogin.com/help/starting-a-profile-with-postman).

## Requirements

1. **Multilogin desktop app** running on the same machine as the RalphAI API (`./run.sh` or your worker).
2. **Operator ↔ profile mapping** (repo root): `operator_multilogin_mapping.json` (+ `.csv`). Regenerate with `python -m multilogin.sync_operator_mapping`. Legacy fallback: `DD_Creds_with_profiles.csv`.
3. **`.env`** (repo root):

```bash
USE_MULTILOGIN=true
MULTILOGIN_USERNAME=your@multilogin-account.com
# Preferred if password contains $ or other shell characters (run.sh sources .env):
MULTILOGIN_PASSWORD_B64=   # base64(UTF-8 password) — see below
# Or plain (must quote for $): MULTILOGIN_PASSWORD='your$password'
# Optional:
# MULTILOGIN_FOLDER_ID=...          # default: first workspace folder
# OPERATOR_PROFILE_MAPPING=operator_multilogin_mapping.json
# MULTILOGIN_PROFILES_CSV=multilogin/DD_Creds_with_profiles.csv  # legacy fallback
# MULTILOGIN_AUTOMATION_TYPE=playwright   # browser-use (default); selenium = WebDriver only
# MULTILOGIN_CDP_URL=ws://127.0.0.1:PORT/devtools/browser/...  # if profile already started manually
```

## Flow

1. Agent run sets `DOORDASH_EMAIL` (from Airtable / operator picker).
2. `shared/multilogin_browser.py` looks up `multilogin_profile_id` in `operator_multilogin_mapping.json`.
3. `multilogin/connect.py` signs in, starts profile with `automation_type=playwright` (CDP for browser-use), proxy/lock retries — not the Selenium driver code from `DoorDash_download_only.py`.
4. browser-use attaches via CDP URL from the launcher port.
5. When downloads finish (or fail/cancel), RalphAI calls Multilogin `GET .../profile/stop/p/{profile_id}` so the profile is no longer “Running” in the app.

## Code layout

| File | Role |
|------|------|
| `connect.py` | Multilogin API connect only (extracted from sample) |
| `DoorDash_download_only.py` | Original reference (not imported by RalphAI) |
| `../shared/operator_profile_mapping.py` | Canonical operator ↔ profile repository |
| `sync_operator_mapping.py` | Build mapping from Airtable + Multilogin API |
| `../shared/multilogin_browser.py` | Email → profile ID + start/stop for agents |

## Two APIs (cloud vs agent) — important

| Base URL | What it does | Where it runs |
|----------|----------------|---------------|
| `https://api.multilogin.com` | Sign-in, workspaces, profile list, proxy updates | **Multilogin cloud** |
| `https://launcher.mlx.yt:45001` | **Start/stop** browser profile, return automation port | **Multilogin Agent** on a machine |

### Endpoints RalphAI uses (`connect.py`)

These match the [Multilogin X Postman collection](https://documenter.getpostman.com/view/28533318/2s946h9Cv9) and your `DoorDash_download_only.py` sample:

| Step | Method | URL |
|------|--------|-----|
| Sign in | `POST` | `{MLX_BASE}/user/signin` — body `{ "email", "password": "<md5 hex of UTF-8 password>" }` → Bearer token ([Postman setup](https://multilogin.com/help/en_US/getting-started-with-postman)) |
| Workspace | `GET` | `{MLX_BASE}/user/workspaces` → `workspace_id` (folder) |
| Start profile (v2) | `GET` | `{MLX_LAUNCHER_V2}/profile/f/{folder_id}/p/{profile_id}/start?automation_type=playwright&headless_mode=false` (browser-use; use `selenium` only for WebDriver scripts) |
| Stop profile | `GET` | `{MLX_LAUNCHER_STOP}/profile/stop/p/{profile_id}` |
| Unlock (on lock error) | `GET` | `{MLX_BASE}/bpds/profile/unlock_profiles` |
| Proxy refresh (on proxy error) | `POST` | `{MLX_BASE}/profile/partial_update` + optional `profile-proxy.multilogin.com` |

After start, the launcher returns `data.port`. RalphAI resolves **CDP** via `http://127.0.0.1:{port}/json/version` → `webSocketDebuggerUrl` for browser-use (same machine as the agent). Selenium would use `http://127.0.0.1:{port}` as `command_executor` per [Multilogin Selenium docs](https://multilogin.com/help/en_US/selenium-automation-example).

RalphAI uses **both**:

1. Cloud: `signin` with `MULTILOGIN_USERNAME` + **MD5 hash** of the real password (RalphAI hashes in `credentials.py`; store plain password in `MULTILOGIN_PASSWORD_B64`, not the MD5).
2. Agent: `GET .../profile/.../start?automation_type=selenium` → browser opens; automation connects to `http://127.0.0.1:<port>` on **that same machine**.

The agent is **not** optional for starting profiles today. Multilogin’s docs state the desktop **agent must be running** (can be on a VM/server, not only your MacBook — but still *some* machine with the agent, not Cloud Run alone).

`127.0.0.1:<port>` in the response is on the **agent host**. Your RalphAI API must run on that same host (or you need a custom remote CDP bridge — not in the stock sample).

## Credentials in `.env`

Encode the Multilogin password as base64 (alphanumeric + `=` only — safe when `run.sh` runs `source .env`):

```bash
python -c "import base64; print(base64.b64encode(b'YOUR_PASSWORD').decode())"
```

Put the output in `.env` as `MULTILOGIN_PASSWORD_B64=...`. RalphAI decodes it in `multilogin/credentials.py` before API sign-in.

- Put secrets only in **local** `.env` (gitignored). **Do not commit** real passwords.
- **No special encryption** before Multilogin API: HTTPS + Bearer token after sign-in (same as your sample).
- `MULTILOGIN_USERNAME` / `MULTILOGIN_PASSWORD` = your **Multilogin account** (e.g. payouts@…), not DoorDash.

## DoorDash credentials when using Multilogin

- **DoorDash login is not used** when `USE_MULTILOGIN=true`: the profile is already logged in.
- `DOORDASH_EMAIL` is still used to pick the **profile ID** from `operator_multilogin_mapping.json`.
- `DOORDASH_PASSWORD` can stay empty for Multilogin runs; Airtable may still supply it — it is ignored for login.
- The agent task opens `https://merchant-portal.doordash.com/merchant/reports` and runs the report flow (same as your sample’s reports URL).

## Export all profile names + IDs (no RalphAI)

Standalone script — only needs `.env` Multilogin credentials and network (desktop app not required):

```bash
# From repo root (loads .env automatically)
python -m multilogin.export_profiles

# Optional: filter by name, custom path, folder
python -m multilogin.export_profiles --search Jeff -o multilogin/profiles_export.csv
```

Writes CSV columns: `profile_name`, `profile_id`, `folder_id`, `browser_type`, `os_type`, `created_at`, `last_used`.

## Bulk-create profiles for unmapped operators

Creates Multilogin profiles for every Airtable operator without a mapping entry:

```bash
# Preview targets (no API calls)
python -m multilogin.bulk_create_profiles --dry-run

# Clone template profile, apply proxy template, update mapping JSON+CSV
python -m multilogin.bulk_create_profiles --refresh-mapping

# First N only
python -m multilogin.bulk_create_profiles --limit 5
```

Defaults (override via `.env` or flags):
- `MULTILOGIN_PROFILE_TEMPLATE_ID` — source profile to clone (fingerprint/settings)
- `MULTILOGIN_PROXY_STRING` — `host:port:username:password` from proxy template manager

Results: `multilogin/bulk_create_results.json`

**Note:** Multilogin clone ignores the `name` field and defaults to `Copy 1 of <source>`.
Bulk create calls `POST /profile/partial_update` with `updates.name` immediately after clone.

Fix already-created profiles:

```bash
python -m multilogin.rename_bulk_profiles
```

Rename API: `POST /profile/partial_update` with top-level `name` (same as `proxy`):
`{"profile_id": "...", "name": "Operator Name"}`.  
Verify: `python -m multilogin.verify_profile_names`  
Note: `updates.name` returns 200 but does **not** change the UI name.

## Sync operator ↔ profile mapping

Builds repo-root `operator_multilogin_mapping.json` from Airtable operators and Multilogin profiles (auto-matches by email, legacy CSV, and normalized operator/profile names):

```bash
# Live Airtable + Multilogin cloud API
python -m multilogin.sync_operator_mapping

# Offline: Airtable disk snapshot + multilogin/profiles_export.csv
python -m multilogin.sync_operator_mapping --offline
```

Unmapped operators or profiles are listed in the JSON. Set `"match_method": "manual"` on a row to preserve hand-edited profile IDs across re-syncs.

For one-off profile exports only, use `export_profiles.py` (see above). Copy `profile_id` into the mapping JSON or re-run sync after updating legacy `DD_Creds_with_profiles.csv`.

## Cloud Run note

Cloud Run cannot reach `launcher.mlx.yt` on your laptop. Run `./run.sh` on the **same machine as the Multilogin agent**, or on a **VM** where the agent is installed.
