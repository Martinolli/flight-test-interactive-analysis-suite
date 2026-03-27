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
- [ ] AI Analysis button on FlightTestDetail
- [ ] Analysis result display (markdown rendering)
- [ ] Natural language search
- [ ] Automated report generation (PDF)
- [ ] Anomaly detection panel

## Phase 6: Performance & Polish
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
