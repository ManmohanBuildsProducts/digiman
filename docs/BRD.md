# Business Requirements Document (BRD)
# Digiman - ADHD Command Center

**Document Version:** 1.0
**Last Updated:** January 30, 2026
**Author:** Manmohan (Product Owner)
**Status:** Production

---

## 1. Executive Summary

**Digiman** is a personal productivity system designed specifically for knowledge workers with ADHD. It automates the capture of action items from meeting notes (Granola) and team communication (Slack), presenting them in a unified interface with flexible timelines.

### The Problem

Knowledge workers with ADHD face unique challenges:
- **Capture Failure:** Forgetting to note action items during meetings
- **Context Switching:** Losing track of commitments across Slack channels
- **Prioritization Paralysis:** Difficulty deciding what to work on today vs. later
- **Time Blindness:** Poor sense of when things are due

### The Solution

Digiman automates the cognitive overhead of task management:
1. **Automatic Capture:** Extracts action items from Granola meeting summaries and Slack @mentions
2. **Triage Inbox:** Surfaces suggestions for review, not immediate action
3. **Flexible Timelines:** Today / This Week / This Month / Backlog (no rigid due dates)
4. **Morning Briefing:** Daily Slack DM with prioritized tasks

---

## 2. Business Objectives

### 2.1 Primary Objective

**Reduce the cognitive load of task management for ADHD knowledge workers by 80%** through automation and intelligent prioritization.

### 2.2 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Inbox Acceptance Rate | >70% | Suggestions accepted / total suggestions |
| Task Completion Rate | >60% | Completed todos / accepted todos |
| Time-to-Triage | <24 hours | Suggestion created → accepted/discarded |
| Daily Active Usage | >5 days/week | Days with at least 1 interaction |
| Capture Coverage | >90% | Actual commitments captured vs. made in meetings |

### 2.3 Business Value

- **Time Saved:** ~30 min/day on manual task capture and review
- **Reduced Anxiety:** Clear visibility into all commitments
- **Improved Reliability:** Fewer dropped balls from forgotten tasks
- **Better Prioritization:** Focus on today's work, not everything

---

## 3. Target Users

### 3.1 Primary Persona

**Name:** Alex, 35, Product Manager
**ADHD Status:** Diagnosed, medicated
**Work Style:** 4-6 meetings/day, heavy Slack usage

**Pain Points:**
- Leaves meetings with verbal commitments, forgets to write them down
- Gets @mentioned in Slack, means to follow up, loses the thread
- Overwhelmed by long todo lists, doesn't know where to start
- Feels guilty about dropped tasks

**Goals:**
- Capture everything automatically
- Start each day knowing exactly what to focus on
- Move tasks flexibly without guilt
- Feel in control, not overwhelmed

### 3.2 Secondary Personas

- **Executive:** Fewer meetings, more strategic tasks, needs weekly view
- **Engineer:** More Slack-heavy, code review requests, technical tasks
- **Founder:** Context-switching between roles, needs ruthless prioritization

---

## 4. Scope

### 4.1 In Scope (MVP - Delivered)

| Feature | Status |
|---------|--------|
| Granola meeting notes ingestion | ✅ Complete |
| Slack @mentions ingestion | ✅ Complete |
| Suggestion inbox (triage view) | ✅ Complete |
| Today view (dashboard) | ✅ Complete |
| Calendar view (monthly) | ✅ Complete |
| Manual todo creation | ✅ Complete |
| Timeline reassignment | ✅ Complete |
| Morning Slack briefing | ✅ Complete |
| macOS menu bar app | ✅ Complete |
| System status monitor | ✅ Complete |
| Web deployment (PythonAnywhere) | ✅ Complete |
| Automated nightly sync | ✅ Complete |

### 4.2 Out of Scope (Future)

| Feature | Priority | Rationale |
|---------|----------|-----------|
| Multi-user / Teams | Low | Personal tool first |
| Mobile app | Medium | Web is responsive enough |
| Google Calendar sync | Medium | Would add external visibility |
| Recurring tasks | Medium | Common need, not MVP |
| AI-powered prioritization | Low | Manual control preferred |
| Email ingestion | Low | Slack covers most cases |

---

## 5. Stakeholders

| Role | Name | Interest |
|------|------|----------|
| Product Owner | Manmohan | Primary user, decision maker |
| Developer | Manmohan + Claude | Implementation |
| End User | Manmohan | Daily usage, feedback |

---

## 6. Constraints

### 6.1 Technical Constraints

- **Granola Dependency:** Requires Granola desktop app running locally
- **Slack Bot Scopes:** Limited by available OAuth scopes
- **PythonAnywhere Free Tier:** Limited CPU, no always-on tasks
- **SQLite:** Single-user, local database only

### 6.2 Business Constraints

- **Solo Development:** Limited time for features
- **No Budget:** Using free tiers only
- **Privacy First:** No cloud sync, self-hosted

---

## 7. Assumptions

1. User has Granola desktop app installed and active
2. User has Slack workspace with bot permissions
3. User's Mac is on during sync times (11 PM, 8 AM)
4. User checks Slack for morning briefing
5. User prefers automation over manual control

---

## 8. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Granola API changes | Medium | High | Monitor updates, abstract ingester |
| Slack rate limits | Low | Medium | Batch requests, respect limits |
| PythonAnywhere downtime | Low | Low | Health monitoring in place |
| Over-extraction (too many suggestions) | Medium | Medium | Tune extraction patterns |
| Under-extraction (missed items) | Medium | High | Allow manual addition |

---

## 9. Dependencies

| Dependency | Type | Risk Level |
|------------|------|------------|
| Granola Desktop App | External | Medium |
| Slack API | External | Low |
| PythonAnywhere | Infrastructure | Low |
| macOS (for menu bar) | Platform | Low |
| Python 3.10+ | Runtime | Low |

---

## 10. Approval

| Role | Name | Date | Signature |
|------|------|------|-----------|
| Product Owner | Manmohan | Jan 30, 2026 | ✅ |

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Suggestion** | Auto-extracted item pending user review |
| **Todo** | Accepted suggestion or manually created task |
| **Timeline** | Due context: date, week, month, or backlog |
| **Triage** | Process of reviewing and accepting/discarding suggestions |
| **Briefing** | Morning Slack DM with today's priorities |
| **Sync** | Automated process to ingest new items from sources |
