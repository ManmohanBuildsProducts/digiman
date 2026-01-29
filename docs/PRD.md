# Product Requirements Document (PRD)
# Digiman - ADHD Command Center

**Document Version:** 1.0
**Last Updated:** January 30, 2026
**Author:** Manmohan
**Status:** Production

---

## 1. Product Overview

### 1.1 Vision Statement

> "Never forget a commitment again. Digiman captures your action items automatically, so you can focus on doing the work instead of tracking it."

### 1.2 Product Summary

Digiman is a personal ADHD command center that:
- **Captures** action items from Granola meetings and Slack mentions
- **Surfaces** them as suggestions for triage
- **Organizes** accepted items into flexible timelines
- **Delivers** daily briefings via Slack

### 1.3 Key Differentiators

| vs. Traditional Todo Apps | Digiman Advantage |
|---------------------------|-------------------|
| Manual entry required | Automatic capture from meetings + Slack |
| Single due date | Flexible timelines (today/week/month/backlog) |
| All items equal priority | Visual grouping (overdue → today → week) |
| No context | Source attribution (meeting name, Slack channel) |
| No automation | Nightly sync + morning briefing |

---

## 2. User Stories

### 2.1 Core Stories (MVP)

#### Capture
| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| C1 | As a user, I want my Granola meeting action items captured automatically | Items appear in inbox within 24 hours of meeting |
| C2 | As a user, I want my Slack @mentions captured automatically | Mentions appear in inbox within 24 hours |
| C3 | As a user, I want to see where each item came from | Source type, meeting name/channel, link shown |

#### Triage
| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| T1 | As a user, I want to review suggestions in an inbox | Dedicated inbox view with all pending suggestions |
| T2 | As a user, I want to accept a suggestion and assign a timeline | Modal with timeline options appears on accept |
| T3 | As a user, I want to discard irrelevant suggestions | One-click discard removes from inbox |

#### Manage
| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| M1 | As a user, I want to see today's priorities at a glance | Today view shows overdue, today, this week |
| M2 | As a user, I want to mark todos complete | Checkbox toggles completion state |
| M3 | As a user, I want to move todos to different timelines | Reassign menu with today/tomorrow/week/month/backlog |
| M4 | As a user, I want to add todos manually | Quick-add form in today view |
| M5 | As a user, I want to see my month at a glance | Calendar view with day-by-day counts |

#### Notify
| ID | Story | Acceptance Criteria |
|----|-------|---------------------|
| N1 | As a user, I want a daily briefing in Slack | DM at 8 AM with overdue, today, week, suggestions |
| N2 | As a user, I want quick access from menu bar | macOS menu bar shows count, click for actions |

### 2.2 Future Stories

| ID | Story | Priority |
|----|-------|----------|
| F1 | As a user, I want recurring tasks | Medium |
| F2 | As a user, I want to add descriptions to todos | Low (implemented) |
| F3 | As a user, I want to see my completion stats | Low |
| F4 | As a user, I want tasks synced to Google Calendar | Medium |
| F5 | As a user, I want to snooze tasks | Low |

---

## 3. Functional Requirements

### 3.1 Data Ingestion

#### FR-ING-01: Granola Ingestion
- **Trigger:** Nightly cron (11 PM)
- **Source:** `~/Library/Application Support/Granola/cache-v3.json`
- **Lookback:** 24 hours
- **Extraction:** Action items from summary panels (regex-based)
- **Deduplication:** By meeting ID in `processed_sources` table
- **Output:** Suggestions with `source_type='granola'`

#### FR-ING-02: Slack Ingestion
- **Trigger:** Nightly cron (11 PM)
- **Source:** Slack Bot API (`conversations.history`)
- **Lookback:** 24 hours
- **Detection:** Messages containing `<@USER_ID>` pattern
- **Context:** Channel name, username, thread replies
- **Deduplication:** By `{channel_id}_{message_ts}` in `processed_sources`
- **Output:** Suggestions with `source_type='slack'`

### 3.2 Suggestion Management

#### FR-SUG-01: Inbox View
- Display all items where `is_suggestion=True` and `status='pending'`
- Group by source type (Granola meetings, Slack mentions)
- Show source context (meeting title, channel name)
- Provide Accept and Discard buttons

#### FR-SUG-02: Accept Flow
- On accept click, show timeline selection modal
- Options: Today, Tomorrow, This Week, This Month, Backlog
- On selection:
  - Set `is_suggestion=False`
  - Set `timeline_type` and appropriate `due_*` field
  - Remove from inbox view
  - Add to appropriate todo view

#### FR-SUG-03: Discard Flow
- On discard click, set `status='discarded'`
- Remove from inbox view
- Do not show in any other view

### 3.3 Todo Management

#### FR-TODO-01: Today View
- **Overdue Section:** Items where `due_date < today` and `status='pending'`
- **Today Section:** Items where `due_date = today` and `status='pending'`
- **This Week Section:** Items where `due_week = current_iso_week` and `status='pending'`
- **Completed Section:** Items where `status='completed'` and `completed_at = today`

#### FR-TODO-02: Calendar View
- Monthly grid showing all dates
- Day cells show count of pending todos
- Highlight overdue days in red
- Click day to see todos for that date
- Bottom sections for weekly, monthly, and backlog items

#### FR-TODO-03: CRUD Operations
| Operation | Endpoint | Behavior |
|-----------|----------|----------|
| Create | `POST /api/todos` | Creates todo with provided fields |
| Read | `GET /api/todos` | Returns filtered list |
| Update | `PATCH /api/todos/:id` | Updates specified fields |
| Delete | `DELETE /api/todos/:id` | Removes todo |
| Toggle | `POST /api/todos/:id/toggle` | Flips completion status |
| Reassign | `POST /api/todos/:id/reassign` | Changes timeline |

### 3.4 Notifications

#### FR-NOT-01: Morning Briefing
- **Trigger:** 8 AM cron job
- **Channel:** Slack DM to configured user
- **Content:**
  ```
  🧠 Digiman Daily Briefing - [Date]

  💡 NEW SUGGESTIONS ([count])
  [List of new suggestions by source]

  🔴 OVERDUE ([count])
  [List with days overdue]

  📅 TODAY ([count])
  [List of today's todos]

  📆 THIS WEEK ([count])
  [List of this week's todos]
  ```

#### FR-NOT-02: Menu Bar Status
- Show todo count in menu bar: `🧠 N`
- When all complete: `🧠 ✓`
- Dropdown shows top 10 todos
- Click todo for quick actions (complete, move to tomorrow)

---

## 4. Non-Functional Requirements

### 4.1 Performance

| Metric | Requirement |
|--------|-------------|
| Page Load | <2 seconds |
| API Response | <500ms |
| Sync Duration | <60 seconds |
| Database Size | <100MB for 10,000 todos |

### 4.2 Reliability

| Metric | Requirement |
|--------|-------------|
| Uptime | 99% (allows ~7 hours downtime/month) |
| Data Loss | Zero (SQLite with WAL mode) |
| Sync Success Rate | >95% |

### 4.3 Security

- No authentication required (single-user, local)
- Slack tokens stored in `.env` (not committed)
- No PII transmitted to external services
- HTTPS enforced on PythonAnywhere

### 4.4 Usability

- Mobile-responsive web UI
- Keyboard shortcuts for common actions
- Clear visual hierarchy (overdue → today → week)
- One-click actions (no multi-step workflows)

---

## 5. Technical Architecture

### 5.1 System Components

```
┌─────────────────────────────────────────────────────────┐
│                      DATA SOURCES                        │
├────────────────────────┬────────────────────────────────┤
│     Granola Cache      │         Slack API              │
│   (Local JSON file)    │    (Bot token, REST API)       │
└───────────┬────────────┴───────────────┬────────────────┘
            │                            │
            ▼                            ▼
┌─────────────────────────────────────────────────────────┐
│                    INGESTION LAYER                       │
│  ┌──────────────────┐    ┌──────────────────┐          │
│  │ GranolaIngester  │    │  SlackIngester   │          │
│  │ - Parse TipTap   │    │ - conversations  │          │
│  │ - Extract items  │    │ - @mention scan  │          │
│  └────────┬─────────┘    └────────┬─────────┘          │
└───────────┼────────────────────────┼────────────────────┘
            │                        │
            ▼                        ▼
┌─────────────────────────────────────────────────────────┐
│                    DATA LAYER                            │
│  ┌────────────────────────────────────────────────────┐ │
│  │                  SQLite Database                    │ │
│  │  ├─ todos (with is_suggestion flag)                │ │
│  │  ├─ sync_history                                   │ │
│  │  └─ processed_sources (dedup)                      │ │
│  └────────────────────────────────────────────────────┘ │
└───────────┬─────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────┐
│                 PRESENTATION LAYER                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │   Web UI     │  │  Menu Bar    │  │   Slack DM   │  │
│  │   (Flask)    │  │   (rumps)    │  │   (API)      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 5.2 Data Model

```sql
-- Core todo table
CREATE TABLE todos (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,

    -- Source tracking
    source_type TEXT NOT NULL,        -- 'granola'|'slack'|'manual'
    source_id TEXT,
    source_context TEXT,
    source_url TEXT,

    -- Timeline
    timeline_type TEXT DEFAULT 'date', -- 'date'|'week'|'month'|'backlog'
    due_date DATE,
    due_week TEXT,                     -- '2026-W05'
    due_month TEXT,                    -- '2026-01'

    -- Status
    status TEXT DEFAULT 'pending',
    is_suggestion BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    completed_at DATETIME
);

-- Deduplication
CREATE TABLE processed_sources (
    source_type TEXT,
    source_id TEXT,
    processed_at DATETIME,
    UNIQUE(source_type, source_id)
);

-- Sync tracking
CREATE TABLE sync_history (
    id INTEGER PRIMARY KEY,
    sync_type TEXT,
    started_at DATETIME,
    completed_at DATETIME,
    items_processed INTEGER,
    items_extracted INTEGER,
    errors TEXT
);
```

### 5.3 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/` | Today view (HTML) |
| GET | `/inbox` | Suggestion triage (HTML) |
| GET | `/calendar` | Calendar view (HTML) |
| GET | `/status` | System status (HTML) |
| GET | `/api/todos` | List todos (JSON) |
| POST | `/api/todos` | Create todo (JSON) |
| GET | `/api/todos/:id` | Get todo (JSON) |
| PATCH | `/api/todos/:id` | Update todo (JSON) |
| DELETE | `/api/todos/:id` | Delete todo (JSON) |
| POST | `/api/todos/:id/toggle` | Toggle completion (JSON) |
| POST | `/api/todos/:id/reassign` | Change timeline (JSON) |
| GET | `/api/suggestions` | List suggestions (JSON) |
| POST | `/api/suggestions/:id/accept` | Accept suggestion (JSON) |
| POST | `/api/suggestions/:id/discard` | Discard suggestion (JSON) |
| POST | `/api/sync` | Trigger manual sync (JSON) |

---

## 6. User Interface

### 6.1 Today View (Primary)

```
┌─────────────────────────────────────────────────────┐
│  🧠 Digiman                    [Inbox] [Calendar]   │
├─────────────────────────────────────────────────────┤
│                                                      │
│  🔴 OVERDUE (2)                                     │
│  ├─ [ ] Fix critical bug (2d)        [Planning]    │
│  └─ [ ] Reply to Sarah (1d)          #dev-team     │
│                                                      │
│  📅 TODAY - Thu, Jan 30                             │
│  ┌─────────────────────────────────────────────┐   │
│  │ + Add a todo...                              │   │
│  └─────────────────────────────────────────────┘   │
│  ├─ [ ] Review design mockups         [1:1 w/]    │
│  ├─ [ ] Prepare demo                  [manual]    │
│  └─ [✓] Send weekly update            [manual]    │
│                                                      │
│  📆 THIS WEEK - W05                                 │
│  ├─ [ ] Schedule 1:1 with team        [Standup]   │
│  └─ [ ] Write Q1 roadmap              [Planning]  │
│                                                      │
│  ✅ COMPLETED TODAY (1)                             │
│  └─ [✓] Send weekly update                         │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 6.2 Inbox View

```
┌─────────────────────────────────────────────────────┐
│  🧠 Digiman                    [Today] [Calendar]   │
├─────────────────────────────────────────────────────┤
│                                                      │
│  💡 NEW SUGGESTIONS (5)                             │
│                                                      │
│  From Meetings:                                      │
│  ┌─────────────────────────────────────────────┐   │
│  │ 📝 Planning Session                          │   │
│  │    • Finalize Q1 roadmap    [Accept][Discard]│   │
│  │    • Schedule user research [Accept][Discard]│   │
│  └─────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────┐   │
│  │ 📝 1:1 with Sarah                            │   │
│  │    • Review her promotion   [Accept][Discard]│   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
│  From Slack:                                         │
│  ┌─────────────────────────────────────────────┐   │
│  │ 💬 #dev-team                                 │   │
│  │    @bob: Can you review PR #456?            │   │
│  │                            [Accept][Discard] │   │
│  └─────────────────────────────────────────────┘   │
│                                                      │
└─────────────────────────────────────────────────────┘
```

### 6.3 Accept Modal

```
┌─────────────────────────────────────┐
│  When should this be done?          │
├─────────────────────────────────────┤
│                                     │
│  [ Today      ]  ← default          │
│  [ Tomorrow   ]                     │
│  [ This Week  ]                     │
│  [ This Month ]                     │
│  [ Backlog    ]                     │
│                                     │
│            [Cancel]  [Accept]       │
└─────────────────────────────────────┘
```

---

## 7. Automation Schedule

| Job | Time | Script | Purpose |
|-----|------|--------|---------|
| Nightly Sync | 11:00 PM | `nightly_sync.py` | Ingest Granola + Slack |
| Morning Push | 8:00 AM | `morning_push.py` | Send Slack briefing |
| Health Check | Every 15 min | GitHub Actions | Monitor uptime |

---

## 8. Configuration

### 8.1 Environment Variables

```env
# Required
SLACK_BOT_TOKEN=xoxb-...
SLACK_USER_ID=U...
FLASK_SECRET_KEY=...

# Optional
GRANOLA_CACHE_PATH=~/Library/Application Support/Granola/cache-v3.json
DATABASE_PATH=./data/todos.db
FLASK_DEBUG=false
```

### 8.2 Slack App Scopes

| Scope | Purpose |
|-------|---------|
| `channels:history` | Read channel messages |
| `channels:read` | List channels |
| `chat:write` | Send DM briefing |
| `users:read` | Get usernames |
| `im:write` | Open DM channel |

---

## 9. Testing Strategy

### 9.1 Test Coverage

| Layer | Tests | Coverage Target |
|-------|-------|-----------------|
| Models | `test_models.py` | >90% |
| Ingesters | `test_granola_ingester.py`, `test_slack_ingester.py` | >80% |
| API | `test_api.py` | >80% |
| Integration | `test_ingesters.py` | >70% |

### 9.2 Test Commands

```bash
# Run all tests
pytest tests/

# With coverage
pytest tests/ --cov=digiman --cov-report=term-missing

# Specific test file
pytest tests/test_api.py -v
```

---

## 10. Deployment

### 10.1 Local Development

```bash
cd ~/Projects/digiman
source venv/bin/activate
python run.py  # http://localhost:5050
```

### 10.2 Production (PythonAnywhere)

- **URL:** `https://manmohanbuildsproducts.pythonanywhere.com`
- **Deploy:** Push to GitHub → Auto-deploy webhook
- **Monitoring:** GitHub Actions health check every 15 min

### 10.3 Menu Bar Apps (macOS)

```bash
# Main app
python menubar/digiman_menubar.py

# Monitor app
python monitor/monitor_app.py
```

---

## 11. Release History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | Jan 30, 2026 | Initial production release |
| 0.9 | Jan 29, 2026 | Added suggestion workflow, inbox view |
| 0.8 | Jan 28, 2026 | Menu bar apps, monitor dashboard |
| 0.7 | Jan 27, 2026 | Calendar view, timeline reassignment |
| 0.5 | Jan 25, 2026 | Granola + Slack ingestion |
| 0.1 | Jan 24, 2026 | Initial Flask app with basic CRUD |

---

## 12. Future Roadmap

### Phase 2 (Q1 2026)
- [ ] Recurring tasks
- [ ] Priority levels (P0/P1/P2)
- [ ] Keyboard shortcuts

### Phase 3 (Q2 2026)
- [ ] Google Calendar sync
- [ ] Email ingestion
- [ ] Weekly review workflow

### Phase 4 (Future)
- [ ] Mobile app (React Native)
- [ ] Team/shared workspaces
- [ ] AI-powered prioritization

---

## 13. Appendix

### A. Glossary

| Term | Definition |
|------|------------|
| **Suggestion** | Auto-extracted item pending user review (`is_suggestion=True`) |
| **Todo** | Accepted task with assigned timeline (`is_suggestion=False`) |
| **Timeline** | When task should be done: date, week, month, or backlog |
| **Triage** | Process of reviewing suggestions in inbox |
| **Briefing** | Morning Slack DM with priorities |
| **Sync** | Automated ingestion of new items |

### B. References

- Granola: https://granola.so
- Slack API: https://api.slack.com
- PythonAnywhere: https://pythonanywhere.com
- HTMX: https://htmx.org
- Tailwind CSS: https://tailwindcss.com
