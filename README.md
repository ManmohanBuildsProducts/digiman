# Digiman - ADHD Command Center

A personal productivity system that extracts action items from Granola meetings and Slack, presenting them in a unified todo view with flexible timelines.

## Features

- **Granola Integration**: Automatically extracts action items from meeting notes
- **Slack Integration**: Captures @mentions and unread threads as potential todos
- **AI Extraction**: Uses Claude API to intelligently identify actionable tasks
- **Flexible Timelines**: Assign todos to today, this week, this month, or backlog
- **Morning Briefing**: Daily Slack DM with your priorities
- **Local Web UI**: Simple, fast interface at http://localhost:5000

## Quick Start

```bash
# 1. Create virtual environment and install dependencies
cd ~/Projects/digiman
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your API keys

# 3. Initialize database
python scripts/setup_db.py

# 4. Start the web UI
python run.py
# Open http://localhost:5000
```

## Configuration

Create a `.env` file with:

```env
# Claude API (for action extraction)
ANTHROPIC_API_KEY=sk-ant-...

# Slack (for ingestion + push)
SLACK_BOT_TOKEN=xoxb-...
SLACK_USER_ID=U...

# Paths (optional - defaults shown)
GRANOLA_CACHE_PATH=~/Library/Application Support/Granola/cache-v3.json
DATABASE_PATH=./data/todos.db
```

### Slack App Setup

Create a Slack app with these scopes:
- `channels:history` - Read channel messages
- `channels:read` - List channels
- `chat:write` - Send DM to self
- `users:read` - Get user info
- `im:write` - Open DM channel
- `search:read` - Search messages

## Usage

### Web UI

- **Today View** (`/`): See overdue, today's, and this week's todos
- **Calendar View** (`/calendar`): Browse by date, week, month, or backlog
- **Add Todos**: Manually add todos from the Today view
- **Reassign**: Click the "..." button to move todos between timelines

### Manual Sync

```bash
# Run the sync manually
python scripts/nightly_sync.py

# Send morning briefing manually
python scripts/morning_push.py
```

### Automated Sync (macOS)

```bash
# Install launchd jobs
chmod +x scripts/install_cron.sh
./scripts/install_cron.sh
```

This schedules:
- **Nightly sync**: 11:00 PM daily
- **Morning push**: 8:00 AM daily

## Architecture

```
┌─────────────────────────────────────────┐
│           NIGHTLY CRON (11 PM)          │
├─────────────────────────────────────────┤
│  Granola Ingester ──┐                   │
│                     ├─→ AI Extractor    │
│  Slack Ingester ────┘         │         │
│                               ▼         │
│                        SQLite Database  │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│           MORNING CRON (8 AM)           │
├─────────────────────────────────────────┤
│         Slack DM Sender                 │
│         (Daily Briefing)                │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│          LOCAL WEB UI (:5000)           │
├─────────────────────────────────────────┤
│  Flask + Jinja + HTMX + Tailwind        │
│  - Today view                           │
│  - Calendar view                        │
│  - Interactive todo management          │
└─────────────────────────────────────────┘
```

## Directory Structure

```
digiman/
├── digiman/
│   ├── app.py              # Flask application
│   ├── config.py           # Configuration
│   ├── models/             # Database models
│   ├── ingesters/          # Data sources
│   ├── extractors/         # AI extraction
│   ├── notifiers/          # Slack push
│   └── templates/          # HTML templates
├── scripts/
│   ├── setup_db.py         # Database init
│   ├── nightly_sync.py     # Cron: 11 PM
│   ├── morning_push.py     # Cron: 8 AM
│   └── install_cron.sh     # Setup launchd
├── data/
│   └── todos.db            # SQLite database
└── tests/
```

## License

Personal use only.
