# FTIAS Frontend — TODO

## Phase 1: Core CRUD Operations

- [x] Dialog UI component
- [x] Textarea UI component
- [x] Toast notification system
- [x] ConfirmDialog component
- [x] FlightTestModal (Create / Edit)
- [x] FlightTestDetail page (view, edit, delete)
- [x] Dashboard — clickable cards navigate to detail
- [x] Dashboard — "New Flight Test" button opens modal
- [x] Dashboard — toast feedback on create
- [x] App.tsx — /flight-tests/:id route
- [x] api.ts — CreateFlightTestData type, 204 handling
- [ ] Pagination for large datasets on Dashboard

## Phase 2: File Upload & Data Import

- [x] Drag-and-drop upload zone component
- [x] File type validation (CSV, Excel)
- [x] File size validation
- [x] Upload progress indicator
- [x] Connect to backend upload endpoint (XHR with progress tracking)
- [ ] CSV column mapping UI (post-upload preview)
- [x] Upload history list per flight test

## Phase 3: Parameter Visualization

- [x] Install chart library (Recharts)
- [x] Parameter list page — fetch from backend
- [x] Line chart component for time-series data
- [x] Scatter plot for correlations
- [x] Multi-parameter overlay chart (up to 8 series)
- [ ] Zoom / pan controls
- [x] Statistical summary panel (min, max, avg, std dev)
- [ ] Export chart as PNG

## Bug Fixes

- [x] Upload: 404 Not Found — wrong URL /upload → /upload-csv
- [x] Profile: 405 Method Not Allowed — added PATCH /api/auth/me to backend
- [x] Upload history: graceful empty array when backend endpoint not yet implemented
- [x] Upload freezes on large CSV (48k rows) — replaced per-row queries with pre-cached params + batched inserts (1,000 rows/batch)
- [x] Login fails after upload freeze — fixed by releasing DB connections properly via batched commits
- [x] Upload History shows empty — now derives history from /parameters endpoint (synthetic record)
- [x] Parameters page 404 — added GET /{id}/parameters and GET /{id}/parameters/data to backend
- [x] Upload merges/appends data instead of replacing on re-upload — backend now deletes existing data points before inserting new ones
- [x] Upload history shows one inflated synthetic record — now shows actual CSV row count + real filename from localStorage
- [x] Correlation chart Y-axis only shows same parameter as X-axis — dropdowns now use full parameters list; Y excludes X selection
- [x] Parameters from different uploads mixed together — resolved by the replace-on-upload fix above
- [x] Time-series chart: dual Y-axes for parameters with different units/scales
  - Left axis: first unit group; Right axis: all other unit groups
  - Right-axis lines rendered with dashed stroke to distinguish visually
  - Tooltip shows value + unit for each series
  - Legend shows axis assignment ("→ right") for right-axis series
  - Axis labels show unit names on both sides
  - Mean reference lines respect correct axis

## Phase 4: Advanced Features

- [x] Date-range filter on Dashboard
- [x] Aircraft-type filter on Dashboard
- [ ] Dark mode toggle
- [x] User profile editing (name, email)
- [x] Export flight tests to CSV
- [ ] Export parameters to Excel
- [x] Settings page (date format, chart defaults, notifications, about)

## Phase 5: LLM Integration

- [x] AI Analysis button on FlightTestDetail
- [x] Analysis result display (structured text rendering)
- [x] Natural language search (AI Standards Query page)
- [ ] Automated report generation (PDF) — Session 6
- [ ] Anomaly detection panel — future

## Phase 6: LLM / RAG Integration

- [x] Migrate PostgreSQL Docker image from postgres:15-alpine to pgvector/pgvector:pg15
- [x] Enable pgvector extension in database
- [x] Install backend Python deps: docling, openai, pgvector, sentence-transformers
- [x] Add DB tables: documents, document_chunks (with vector(1536) embedding column)
- [x] Backend router: POST /api/documents/upload (Docling parse + chunk + embed + store)
- [x] Backend router: GET /api/documents (list all documents)
- [x] Backend router: DELETE /api/documents/{id} (remove doc + chunks)
- [x] Backend router: POST /api/documents/query (semantic search + LLM answer)
- [x] Backend router: POST /api/flight-tests/{id}/ai-analysis (stats-based AI report)
- [x] Frontend: Document Library page (upload, list, delete standards/handbooks)
- [x] Frontend: AI Standards Query page (chat-style semantic search)
- [x] Frontend: AI Analysis panel on FlightTestDetail page
- [x] Frontend: Sidebar navigation — grouped with 'AI & Documents' section
- [x] Update docker-compose.yml and all project MD docs
- [x] Project_Documents/40_RAG_System_Implementation_Phase6.md created

## Session 5: Bug Fixes and Full Verification (April 3, 2026)

- [x] Fix useToast API mismatch in DocumentLibrary.tsx (showToast/ToastContainer → toasts/dismiss/success/error)
- [x] Fix ConfirmDialog prop mismatch in DocumentLibrary.tsx (onCancel → onClose; remove variant prop)
- [x] Fix TimeSeriesChart prop names in FlightTestDetail.tsx (data→series, showMean→showReferenceMean)
- [x] Replace placeholder ParametersPanel with real component fetching live API data
- [x] Add OPENAI_API_KEY to docker-compose.yml environment pass-through
- [x] Install libxcb1 and GL libraries in Docker container for Docling PDF rendering
- [x] Add system libraries to docker/backend.Dockerfile for future image rebuilds
- [x] Full end-to-end verification: all pages and features confirmed working
- [x] Project_Documents/41_Next_Steps_Roadmap_Session5.md created

## Session 6: Planned (Next Session)

- [ ] Rebuild Docker image (docker compose build --no-cache backend) to make libxcb1 persistent
- [ ] Replace Docling with pymupdf4llm for faster PDF parsing (seconds vs minutes)
- [ ] Implement background task queue for PDF uploads (FastAPI BackgroundTasks)
- [ ] User management panel (admin UI: create user, reset password, assign role)
- [ ] Automated PDF report export from AI Analysis panel (reportlab or weasyprint)
- [ ] Unit tests for documents router (backend/tests/test_documents.py)

## Phase 5: Performance & Polish

- [ ] React Query data caching
- [ ] Lazy-loaded routes
- [ ] Global error boundary
- [ ] Skeleton loaders for all pages
- [ ] Accessibility audit (ARIA, keyboard nav)
- [ ] Unit tests for components
- [ ] E2E tests for critical flows

## Phase 7: Deployment

- [ ] Production build configuration
- [ ] Environment variable setup
- [ ] CI/CD pipeline
- [ ] Deployment documentation
