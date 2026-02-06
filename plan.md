# Digiman — Suspension & Improvement Plan

## Date: 2026-02-06

## What We Did Today

### System Suspension (Complete)
Everything has been suspended to allow for local improvements before reactivating.

1. **Local cron jobs** — All unloaded and removed via `scripts/uninstall_crons.sh`
   - Nightly sync (11 PM)
   - Morning push (8 AM)
   - Smart paste, watchdog, onwake
2. **Menubar app** — Stopped (`com.digiman.menubar`)
3. **Monitor app** — Stopped (`com.digiman.monitor`)
4. **PythonAnywhere web app** — Disabled via API (`whileyousleep.xyz` returns 404)
5. **PythonAnywhere account** — Kept active ($5/mo) to preserve deployment setup

### Current Cost While Suspended
- **PythonAnywhere**: ~$5/mo (Hacker plan, keeping deployment intact)
- **Domain**: ~$10-15/yr auto-renewal for `whileyousleep.xyz`
- **Everything else**: $0 (no API calls being made)

## System Architecture (Reference)

| Component | Location | Purpose |
|---|---|---|
| Nightly Sync | `scripts/nightly_sync.py` | Granola + Slack ingestion → AI extraction → SQLite → cloud push |
| Morning Push | `scripts/morning_push.py` | Daily briefing to `#mydailyplanner` on Slack |
| Menubar App | `menubar/digiman_menubar.py` | macOS menubar status widget |
| Monitor App | `monitor/monitor_app.py` | Background monitoring daemon |
| Flask Web UI | `digiman/app.py` | Local dashboard on :5000 |
| PythonAnywhere | `www.whileyousleep.xyz` | Cloud-hosted dashboard |
| AI Extraction | `digiman/extractors/action_extractor.py` | Ollama (primary) → Anthropic Haiku (fallback) |
| Slack Integration | `digiman/ingesters/slack.py` + `digiman/notifiers/slack_push.py` | Ingest mentions + send briefings |
| SQLite DB | `data/todos.db` | Local todo storage |

## Areas to Improve (To Be Decided)

Potential focus areas for the next phase:

- **Workflow / Pipeline** — Improve ingestion, extraction, sync logic, cron reliability
- **UI / Dashboard** — Improve Flask web UI design, features, usability
- **AI Extraction** — Better action item quality from meetings/Slack (prompts, models, filtering)
- **Architecture** — Simplify, clean up, refactor overall structure

## How to Reactivate

1. **Local crons**: `bash scripts/install_crons.sh`
2. **Menubar/Monitor**: `launchctl load` their plists from `~/Library/LaunchAgents/`
3. **PythonAnywhere**:
   ```bash
   curl -X POST -H "Authorization: Token <API_TOKEN>" \
     "https://www.pythonanywhere.com/api/v0/user/manmohanbuildsproducts/webapps/www.whileyousleep.xyz/enable/"
   ```
   Or enable from the PythonAnywhere dashboard.
