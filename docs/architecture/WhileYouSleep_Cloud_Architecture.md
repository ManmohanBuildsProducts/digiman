# Plan: Laptop-Independent WhileYouSleep Architecture

**Status: FUTURE WORK** - Documented for later implementation. Current laptop-based system stays as-is.

## Decision (Jan 30, 2026)

**Stay laptop-based for now.** Reasons:
- Backfill logic already handles gaps when laptop is off
- Cloud architecture adds complexity and cost (~$5-10/mo)
- Current system is free and works well

**For travel/offline periods:** Just close laptop. When it comes back online, the on-wake trigger + backfill will process all pending meetings automatically.

---

## Future Cloud Architecture (When Needed)

### Problem Statement

Current system requires laptop to be on for:
1. Accessing Granola's local cache (`~/Library/Application Support/Granola/cache-v3.json`)
2. Running Claude Code CLI for SMART_PASTE processing
3. Scheduled cron jobs

## Constraints

- **Budget:** Minimal/no additional cost
- **Granola:** Strictly local, no native cloud sync
- **Claude Code CLI:** Requires local terminal
- **Already have:** PythonAnywhere $10/month (includes scheduled tasks)

## Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LAPTOP (when available)                      │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │ Granola App     │───▶│ granola_sync.py │───▶│ GitHub Private  │  │
│  │ (local cache)   │    │ (every 15 min)  │    │ Repo            │  │
│  └─────────────────┘    └─────────────────┘    └────────┬────────┘  │
│                                                          │           │
│  On wake/startup: Check & re-sync if incomplete          │           │
└──────────────────────────────────────────────────────────┼───────────┘
                                                           │
                                                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         CLOUD (always on)                            │
├─────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │
│  │ GitHub Repo     │───▶│ PythonAnywhere  │───▶│ WhileYouSleep   │  │
│  │ (Granola data)  │    │ Scheduled Task  │    │ Web App         │  │
│  └─────────────────┘    │ (2:00 AM daily) │    │ (todos/inbox)   │  │
│                         │                 │    └─────────────────┘  │
│                         │ Uses Claude API │                          │
│                         │ (not CLI)       │                          │
│                         └─────────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
```

## Key Changes

| Component | Current (Laptop) | New (Cloud) |
|-----------|------------------|-------------|
| Granola data | Local only | Synced to GitHub |
| Meeting processing | Claude Code CLI | Claude API |
| Scheduled tasks | launchd (local) | PythonAnywhere tasks |
| State management | Local files | GitHub + PythonAnywhere |

## Cost Analysis

| Item | Cost |
|------|------|
| PythonAnywhere | $10/month (already paying) |
| GitHub Private Repo | Free |
| Claude API (Sonnet) | ~$0.01-0.05 per meeting |
| **Estimated monthly** | **~$10-12 total** |

## Implementation Steps

### Step 1: Create Private GitHub Repo for Granola Data
- Repo: `ManmohanBuildsProducts/granola-sync` (private)
- Contains: `cache-v3.json`, `sync_state.json`

### Step 2: Local Granola Sync Script
Create `/Users/mac/Projects/digiman/scripts/granola_to_github.py`:
- Runs every 15 minutes (launchd)
- Copies Granola cache to local git repo
- Commits & pushes to GitHub
- Tracks sync state (last_sync, in_progress_meetings)

### Step 3: On-Wake Re-sync Check
- launchd trigger on wake
- Check if last sync completed successfully
- Re-push if laptop shut down mid-sync

### Step 4: Cloud Processing on PythonAnywhere
Modify `scripts/nightly_sync.py` to:
- Pull latest Granola data from GitHub
- Use Claude API (not CLI) for SMART_PASTE processing
- Process only completed meetings (skip in-progress)
- Run as PythonAnywhere scheduled task at 2:00 AM

### Step 5: Handle In-Progress Meetings
- Granola has no "end_time" field
- Heuristic: Meeting is "complete" if no updates in last 2 hours
- Or: Only process meetings from previous day (safe window)

## Files to Create/Modify

### New Files
1. `scripts/granola_to_github.py` - Sync Granola cache to GitHub
2. `scripts/cloud_processor.py` - Claude API-based meeting processor

### Modified Files
3. `scripts/nightly_sync.py` - Pull from GitHub, use Claude API
4. `digiman/config.py` - Add ANTHROPIC_API_KEY, GITHUB_TOKEN
5. `scripts/smart_paste/install_crons.sh` - Add granola-sync launchd plist

### PythonAnywhere
6. Set up scheduled task for 2:00 AM
7. Add environment variables (ANTHROPIC_API_KEY, GITHUB_TOKEN)

## Open Questions (for future)

1. **GitHub vs S3:** GitHub is free and simple. S3 would cost money. OK with GitHub?

2. **Claude API cost:** ~$0.01-0.05 per meeting. For 5 meetings/day = ~$5-10/month. Acceptable?

3. **Processing delay:** With this architecture, meetings are processed once daily (2 AM). Real-time processing would require more complex setup. OK with daily batch?

4. **In-progress meetings:** Should we:
   - Skip meetings with updates in last 2 hours (might miss some)
   - Only process previous day's meetings (guaranteed complete)
   - Process all and re-process next day if incomplete

## Verification Checklist

1. Push Granola cache to GitHub manually, verify it arrives
2. Test Claude API processing on PythonAnywhere console
3. Set up scheduled task, verify it runs at 2:00 AM
4. Test on-wake re-sync when laptop wakes up
5. Verify todos appear in WhileYouSleep web app

## Rollback

If cloud processing fails:
- Laptop-based processing still works when laptop is on
- Dashboard continues to function
- Manual sync always available via web UI
