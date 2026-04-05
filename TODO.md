# FTIAS — Development TODO
**Last updated:** 2026-04-05

This file tracks all features, fixes, and tasks. Completed items are kept as history.

---

## Completed

- [x] Project scaffolding (FastAPI + PostgreSQL + React + Docker)
- [x] User registration and JWT authentication
- [x] Flight test creation and management (CRUD)
- [x] CSV upload with batched background processing
- [x] Parameter time-series charts (full dataset, min-max downsampling)
- [x] Binary/step charts for discrete sensors (Weight-on-Wheels)
- [x] Correlation chart (X vs Y scatter)
- [x] RAG pipeline — document ingestion with Docling + pgvector
- [x] Document library UI with polling status updates
- [x] AI Analysis with RAG (document-grounded, per flight test)
- [x] PDF Report Export (download + browser print)
- [x] Admin User Management panel (create, activate, deactivate, delete)
- [x] Fast bulk delete for large flight test datasets
- [x] DEBUG env var parser fix (string → bool)
- [x] Docker image rebuilt — all system libs baked in (libxcb1, libgl1)
- [x] reportlab baked into Docker image
- [x] Chart Y-axis fix for binary/zero-value parameters
- [x] PDF print dialog fix (afterprint cleanup)
- [x] Create User button in Admin panel

---

## Phase A — Quick Wins

- [ ] A1: Chart PNG download button (TimeSeriesChart, CorrelationChart)
- [ ] A2: Contextual AI prompt box with quick-prompt chips (Takeoff, Landing, Climb, Vibration, General)

---

## Phase B — Core Analysis Features

- [ ] B1: 3D Trajectory tab (Lat/Long/Alt) with Plotly.js, colour-coded by user-selected variable
- [ ] B2: Flight Test Comparison page — overlay same parameter across multiple flight tests

---

## Phase C — Data Export & Enhanced Reporting

- [ ] C1: Export parameter data to CSV (client-side) and Excel (backend openpyxl)
- [ ] C2: Enhanced PDF report — embed trajectory screenshot and parameter chart images

---

## Phase D — Operations & Infrastructure

- [ ] D1: Email notifications (new user registered, document processing complete)
- [ ] D2: Unit tests for documents router (pytest, mock Docling + OpenAI)
- [ ] D3: Celery/Redis task queue *(defer — not needed for single-worker setup)*
