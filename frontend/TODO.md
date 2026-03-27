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
