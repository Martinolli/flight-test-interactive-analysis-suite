# FTIAS — Master Development Roadmap
**Document:** 45 | **Date:** 2026-04-05 | **Status:** Active — Living Document

---

## Project Status Summary

The FTIAS application is fully operational as of Session 7 (2026-04-05). All core infrastructure is stable, the Docker images are rebuilt with all dependencies baked in, and the following features are confirmed working in production.

---

## Completed Features

| # | Feature | Session | Commit |
|---|---|---|---|
| 1 | Project scaffolding (FastAPI + PostgreSQL + React + Docker) | 1–3 | — |
| 2 | User registration and JWT authentication | 3 | — |
| 3 | Flight test creation and management (CRUD) | 3–4 | — |
| 4 | CSV upload with batched background processing | 6 | `fc3d99b` |
| 5 | Parameter time-series charts (full dataset, min-max downsampling) | 7b | `bb71f8f` |
| 6 | Binary/step charts for discrete sensors (Weight-on-Wheels) | 7 / 7b | `d1a11b6` / `bb71f8f` |
| 7 | Correlation chart (X vs Y scatter) | 4–5 | — |
| 8 | RAG pipeline — document ingestion with Docling + pgvector | 5–6 | `fc3d99b` |
| 9 | Document library UI with polling status updates | 6 | `fc3d99b` |
| 10 | AI Analysis with RAG (document-grounded, per flight test) | 5 | — |
| 11 | PDF Report Export (download + browser print) | 7 | `25b5f26` |
| 12 | Admin User Management panel (create, activate, deactivate, delete) | 7 | `25b5f26` |
| 13 | Fast bulk delete for large flight test datasets | 7b | `bb71f8f` |
| 14 | `DEBUG` env var parser fix (string → bool) | 6 | `fc3d99b` |
| 15 | Docker image rebuilt — all system libs baked in | 6–7 | `db55b91` |

---

## Upcoming Roadmap

Items are ordered by value, dependency, and effort. Each phase is self-contained and can be delivered in a single development session.

---

### Phase A — Quick Wins (No new infrastructure required)

#### A1 — Chart PNG Download *(Next)*
Add a **"Download PNG"** button to every time-series and correlation chart panel. The button captures the chart DOM node as a PNG image using `html2canvas` and triggers a browser download. Filename convention: `FTIAS_{ParameterName}_{FlightTestName}_{Date}.png`.

- **Scope:** Frontend only (`TimeSeriesChart.tsx`, `CorrelationChart.tsx`, `Parameters.tsx`)
- **Dependencies:** None
- **Effort:** ~2 hours

#### A2 — Contextual AI Prompt with Quick-Prompt Chips
Replace the fixed "Generate Report" button with a **free-text prompt box**. The user types their analysis goal (e.g., "Analyse takeoff performance and compute ground roll distance"). A row of **quick-prompt chips** pre-fills common requests:

- Takeoff Performance
- Landing Performance
- Climb Performance
- Vibration & Structural Loads
- General Flight Summary

The AI uses the user's prompt as the analysis goal, with the selected parameter statistics and RAG document context as background.

- **Scope:** Backend (`routers/flight_tests.py` — add `user_prompt` field to AI analysis endpoint) + Frontend (`FlightTestDetail.tsx`)
- **Dependencies:** None
- **Effort:** ~3 hours

---

### Phase B — Core Analysis Features

#### B1 — 3D Trajectory Tab (Lat / Long / Altitude)
New **"Trajectory"** tab inside the Flight Test Detail page (alongside Dashboard, Upload Data, Parameters). Renders an interactive 3D line chart using **Plotly.js** showing the aircraft's spatial path.

Features:
- Auto-detects `LATITUDE`, `LONGITUDE`, and `ALTITUDE` columns by name pattern
- Manual override selector for non-standard column names
- Colour-codes the trajectory by a user-selected variable (e.g., Ground Speed) to show performance at each spatial point
- Plotly's built-in toolbar provides free PNG download, zoom, rotate, and pan

- **Scope:** Frontend only (new `Trajectory.tsx` tab component, `FlightTestDetail.tsx` routing)
- **Dependencies:** `plotly.js` + `react-plotly.js` npm packages
- **Effort:** ~3 hours

#### B2 — Flight Test Comparison View
New **"Compare"** page (accessible from the sidebar) that lets the user select two or more flight tests and overlay the same parameter across all of them on a single chart. Essential for before/after configuration comparisons (e.g., comparing takeoff roll distance between two test days).

Features:
- Multi-test selector (up to 4 flight tests)
- Parameter selector (one parameter at a time, overlaid across all selected tests)
- Statistics comparison table (min, max, mean, std dev side-by-side)
- Export comparison chart as PNG (uses A1 infrastructure)

- **Scope:** Backend (new endpoint accepting multiple `test_id` values) + Frontend (new `Compare.tsx` page)
- **Dependencies:** A1 recommended (for chart export)
- **Effort:** ~4 hours

---

### Phase C — Data Export & Enhanced Reporting

#### C1 — Export Parameter Data to CSV/Excel
**"Download CSV"** and **"Download Excel"** buttons on the Parameters page. Exports the currently selected parameters with full time-series data and a statistics header row.

- CSV: generated client-side (no backend needed)
- Excel: backend generates via `openpyxl` for proper column formatting, units in header, and a separate "Statistics" sheet

- **Scope:** Frontend (CSV) + Backend (Excel endpoint in `flight_tests.py`)
- **Dependencies:** None
- **Effort:** ~2 hours

#### C2 — Enhanced PDF Report
Extend the existing PDF export to include:
- The 3D trajectory chart (screenshot via Plotly's built-in export)
- The parameter time-series charts (screenshots via A1 infrastructure)
- A "Selected Parameters" section with chart images embedded before the statistics table

- **Scope:** Backend (`admin.py` PDF builder) + Frontend (pass chart images to PDF endpoint)
- **Dependencies:** A1 (chart PNG download), B1 (3D trajectory)
- **Effort:** ~3 hours

---

### Phase D — Operations & Infrastructure

#### D1 — Email Notifications
Alert the admin when:
- A new user registers
- A document finishes processing (success or error)

Requires SMTP configuration. Recommended approach: use Python's built-in `smtplib` with an environment variable for SMTP credentials, or integrate SendGrid/Mailgun for reliability.

- **Scope:** Backend only (new `notifications.py` helper, hooks in `auth.py` and `documents.py`)
- **Dependencies:** SMTP credentials from user
- **Effort:** ~2 hours

#### D2 — Unit Tests for Documents Router
Add `backend/tests/test_documents.py` with pytest tests covering upload, list, delete, and query endpoints. Mocks the Docling parser and OpenAI embedding calls.

- **Scope:** Backend only
- **Dependencies:** None
- **Effort:** ~2 hours

#### D3 — Celery/Redis Task Queue *(Defer)*
Only needed if multiple backend workers or job persistence across container restarts is required. FastAPI `BackgroundTasks` is sufficient for the current single-worker setup. Defer until the application scales beyond a single-user deployment.

- **Scope:** Backend + Docker Compose
- **Dependencies:** Redis container
- **Effort:** ~1 day

---

## Delivery Sequence

| Order | Item | Phase | Effort | Depends On |
|---|---|---|---|---|
| 1 | Chart PNG Download | A1 | ~2 h | — |
| 2 | Contextual AI Prompt | A2 | ~3 h | — |
| 3 | 3D Trajectory Tab | B1 | ~3 h | — |
| 4 | Flight Test Comparison | B2 | ~4 h | A1 recommended |
| 5 | Export CSV/Excel | C1 | ~2 h | — |
| 6 | Enhanced PDF Report | C2 | ~3 h | A1, B1 |
| 7 | Email Notifications | D1 | ~2 h | SMTP credentials |
| 8 | Unit Tests (Documents) | D2 | ~2 h | — |
| 9 | Celery/Redis Queue | D3 | ~1 day | Defer |

**Total estimated remaining effort: ~21 hours across 7–9 sessions**

---

## Architecture Reference

```
ftias-postgres          PostgreSQL 15 + pgvector
ftias-backend           FastAPI 0.110 / Python 3.11
  ├── /api/auth         JWT authentication
  ├── /api/users        User CRUD
  ├── /api/flight-tests Flight test + CSV upload + AI analysis
  ├── /api/parameters   Parameter metadata
  ├── /api/documents    Document ingestion + RAG query
  └── /api/admin        Admin user management + PDF export
ftias-frontend          React 18 + Vite + TypeScript
  ├── /                 Dashboard
  ├── /flight-tests     Flight test list
  ├── /flight-tests/:id Detail (Dashboard / Upload / Parameters / Trajectory*)
  ├── /parameters       Parameters & charts
  ├── /compare*         Flight test comparison
  ├── /documents        Document library
  └── /admin/users      Admin user management
```
*Items marked with `*` are planned but not yet implemented.*

---

*This document supersedes `41_Next_Steps_Roadmap_Session5.md` and `35_FTIAS_Development_Roadmap_Next_Steps.md` as the single source of truth for the FTIAS development roadmap.*
