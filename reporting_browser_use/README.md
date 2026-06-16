# reporting_browser_use

Standalone DoorDash reporting pipeline using [browser-use](https://github.com/browser-use/browser-use) with a **local Chrome browser** (no Multilogin).

Downloads Financial + Marketing reports, runs analysis, creates campaigns, and optionally pushes results to Google Sheets and Slack.

## Quick start

```bash
cd reporting_browser_use
cp .env.example .env
# Edit .env: DOORDASH_EMAIL, DOORDASH_PASSWORD, GEMINI_API_KEY

chmod +x run.sh
./run.sh
```

## Requirements

- Python 3.11+
- Google Chrome installed (macOS/Linux/Windows)
- `GEMINI_API_KEY` from [Google AI Studio](https://aistudio.google.com/apikey)

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DOORDASH_EMAIL` | Yes | Merchant portal login |
| `DOORDASH_PASSWORD` | Yes | Merchant portal password |
| `GEMINI_API_KEY` | Yes | LLM for browser-use agent |
| `LOCAL_BROWSER_CDP_URL` | No | e.g. `http://localhost:9222` — attach to existing Chrome |
| `CHROME_USER_DATA_DIR` | No | Persistent Chrome profile (default: `.cursor/chrome-debug-profile`) |
| `GOOGLE_SPREADSHEET_ID` | No | Push combined report to existing sheet |
| `GCP_CREDENTIALS_PATH` | No | Service account JSON for Sheets API |
| `SLACK_WEBHOOK_URL` | No | Slack alerts on login/campaign progress |
| `OPERATOR_NAME` | No | Label in analysis output (default: `TODC`) |
| `MAX_CAMPAIGNS_PER_SESSION` | No | Browser restart interval (default: `5`) |
| `FORCE_FULL_RUN` | No | Skip auto-resume of pending campaigns |

## Browser modes

1. **Default** — launches local Chrome with a persistent profile (cookies survive across runs; complete 2FA once manually).
2. **CDP** — set `LOCAL_BROWSER_CDP_URL=http://localhost:9222`; `run.sh` starts Chrome if needed.

## Campaign slots

Copy the example slot grid for slots-based campaign creation:

```bash
cp slots.csv.example slots.csv
```

Without `slots.csv`, campaigns are derived from the combined analysis Excel file.

## Manual run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=.
python main.py
```

Report download only:

```bash
PYTHONPATH=. python run_browser_use.py
```

## Output

- `downloads/{email}-{timestamp}/` — reports, analysis, combined Excel
- `logs/run_*.log` — structured run logs
