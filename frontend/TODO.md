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
- [ ] Install chart library (Recharts)
- [ ] Parameter list page — fetch from backend
- [ ] Line chart component for time-series data
- [ ] Scatter plot for correlations
- [ ] Multi-parameter overlay chart
- [ ] Zoom / pan controls
- [ ] Statistical summary panel (min, max, avg, std dev)
- [ ] Export chart as PNG

## Phase 4: Advanced Features
- [ ] Date-range filter on Dashboard
- [ ] Aircraft-type filter on Dashboard
- [ ] Dark mode toggle
- [ ] User profile editing (name, email)
- [ ] Export flight tests to CSV
- [ ] Export parameters to Excel

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
