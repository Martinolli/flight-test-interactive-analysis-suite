# Frontend Analysis and Required Changes

**Document Number:** 34
**Date:** February 10, 2026
**Author:** Manus AI
**Project:** Flight Test Interactive Analysis Suite (FTIAS)
**Repository:** https://github.com/Martinolli/flight-test-interactive-analysis-suite

---

## Executive Summary

This document provides a comprehensive analysis of the FTIAS frontend application currently deployed in the repository. The frontend is a React-based web application built with modern technologies including TypeScript, Vite, tRPC, and TailwindCSS. While the application successfully loads and displays the authentication screen, it requires integration with the existing FastAPI backend to become fully functional.

**Current Status:** ✅ Frontend deployed and running at `http://localhost:3000`
**Authentication:** Currently configured for Manus OAuth (needs backend integration)
**API Layer:** tRPC-based (needs adapter to connect to FastAPI REST endpoints)

---

## 1. Frontend Architecture Overview

The FTIAS frontend follows a modern React architecture with clear separation of concerns and a component-based structure.

### Technology Stack

| Technology | Version | Purpose |
| ---------- | ------- | ------- |
| **React** | 19.2.1 | UI library for building interactive interfaces |
| **TypeScript** | 5.9.3 | Type-safe JavaScript for better developer experience |
| **Vite** | 7.1.7 | Fast build tool and development server |
| **tRPC** | 11.6.0 | End-to-end typesafe APIs |
| **TailwindCSS** | 4.1.14 | Utility-first CSS framework |
| **Tanstack Query** | 5.90.2 | Data fetching and state management |
| **Recharts** | 2.15.2 | Data visualization library for charts |
| **Wouter** | 3.3.5 | Lightweight routing library |
| **Drizzle ORM** | 0.44.5 | TypeScript ORM for database operations |

### Project Structure

The frontend is organized into the following directory structure:

```bash

frontend/
├── client/                    # Frontend React application
│   ├── public/               # Static assets
│   └── src/
│       ├── _core/            # Core utilities and hooks
│       │   └── hooks/        # React hooks (useAuth, etc.)
│       ├── components/       # Reusable UI components
│       │   ├── ui/          # shadcn/ui component library
│       │   ├── DashboardLayout.tsx
│       │   ├── ErrorBoundary.tsx
│       │   └── Map.tsx
│       ├── contexts/         # React contexts (Theme, etc.)
│       ├── hooks/            # Custom React hooks
│       ├── lib/              # Utility libraries
│       │   ├── trpc.ts      # tRPC client configuration
│       │   └── utils.ts     # Utility functions
│       ├── pages/            # Page components
│       │   ├── Home.tsx     # Dashboard/landing page
│       │   ├── Upload.tsx   # CSV/Excel upload interface
│       │   ├── Parameters.tsx
│       │   ├── Profile.tsx
│       │   ├── Settings.tsx
│       │   └── FlightTestDetail.tsx
│       ├── App.tsx           # Main app component with routing
│       ├── main.tsx          # Application entry point
│       ├── const.ts          # Constants and configuration
│       └── index.css         # Global styles
├── server/                    # Backend tRPC server
│   ├── _core/                # Core server utilities
│   │   ├── context.ts        # tRPC context
│   │   ├── trpc.ts           # tRPC router setup
│   │   ├── oauth.ts          # Manus OAuth integration
│   │   └── env.ts            # Environment variables
│   ├── db.ts                 # Database query helpers
│   ├── routers.ts            # tRPC API routes
│   └── storage.ts            # S3 storage helpers
├── drizzle/                   # Database schema and migrations
│   ├── schema.ts             # Database table definitions
│   └── migrations/           # SQL migration files
├── shared/                    # Shared types and constants
│   ├── const.ts
│   └── types.ts
└── Configuration files
    ├── package.json
    ├── tsconfig.json
    ├── vite.config.ts
    └── drizzle.config.ts
```

---

## 2. Current Implementation Status

### ✅ Completed Features

The frontend application has the following features fully implemented:

***Authentication System**

- Manus OAuth integration with session cookie management
- Protected route wrapper for authenticated pages
- User authentication state management via `useAuth()` hook
- Automatic redirect to login for unauthorized users
- Logout functionality

***Dashboard Layout**

- Professional sidebar navigation with menu items
- Responsive design for desktop and tablet
- User profile display in sidebar
- Theme context for light/dark mode support
- Error boundary for graceful error handling

***Flight Test Management Pages**

- **Home/Dashboard** (`/`) - Flight test list view with search and filtering
- **Flight Test Detail** (`/flight-test/:id`) - Detailed view with data visualization
- **Upload** (`/upload`) - CSV and Excel file upload interface
- **Parameters** (`/parameters`) - Parameter management page
- **Profile** (`/profile`) - User profile information
- **Settings** (`/settings`) - Application settings and preferences

***UI Components**

- Complete shadcn/ui component library (50+ components)
- Custom components:
  - `DashboardLayout` - Main layout with sidebar
  - `ErrorBoundary` - Error handling wrapper
  - `Map` - Google Maps integration
  - `AIChatBox` - AI chat interface

***Data Visualization**

- Recharts integration for time-series charts
- Interactive charts with zoom and pan capabilities
- Parameter selection dropdown for multi-parameter visualization
- Data point statistics display

***File Upload Interface**

- Drag-and-drop file upload components
- File validation and format checking
- Upload success/error feedback with toast notifications
- Support for CSV and Excel file formats

### ⚠️ Pending Integration

The following features are implemented in the UI but require backend integration:

***API Integration**

- tRPC procedures defined but not connected to FastAPI backend
- Database queries implemented but using Manus database (needs migration to PostgreSQL)
- File upload endpoints need backend processing logic

***Authentication**

- Currently using Manus OAuth (needs integration with FastAPI JWT auth)
- User session management needs to connect to backend `/api/auth/login` endpoint

***Data Operations**

- Flight test CRUD operations need REST API integration
- Parameter management needs backend endpoints
- Data point retrieval needs pagination and filtering support

---

## 3. Database Schema Analysis

The frontend includes a comprehensive database schema defined in `drizzle/schema.ts`. This schema needs to be aligned with the existing PostgreSQL backend.

### Current Frontend Schema

```typescript
// Users table (from Manus OAuth)
users {
  id: int (PK, auto-increment)
  openId: varchar(64) unique
  name: text
  email: varchar(320)
  loginMethod: varchar(64)
  role: enum('user', 'admin')
  createdAt: timestamp
  updatedAt: timestamp
  lastSignedIn: timestamp
}

// Flight Tests table
flightTests {
  id: int (PK, auto-increment)
  name: varchar(255)
  description: text
  testDate: date
  aircraft: varchar(100)
  status: enum('planned', 'in-progress', 'completed', 'cancelled')
  createdById: int (FK → users.id)
  createdAt: timestamp
  updatedAt: timestamp
}

// Test Parameters table
testParameters {
  id: int (PK, auto-increment)
  name: varchar(255)
  unit: varchar(50)
  description: text
  parameterType: enum('continuous', 'discrete', 'boolean')
  createdAt: timestamp
}

// Data Points table
dataPoints {
  id: int (PK, auto-increment)
  flightTestId: int (FK → flightTests.id)
  parameterId: int (FK → testParameters.id)
  timestamp: datetime
  value: decimal(20, 6)
  createdAt: timestamp
}
```

### Backend Schema Comparison

The existing FastAPI backend has a similar but not identical schema:

| Table | Frontend | Backend | Status |
| -------|----------|---------|--------|
| **Users** | Manus OAuth schema | FastAPI JWT schema | ⚠️ **Needs alignment** |
| **FlightTests** | `flightTests` | `flight_tests` | ✅ **Compatible** |
| **Parameters** | `testParameters` | `test_parameters` | ✅ **Compatible** |
| **DataPoints** | `dataPoints` | `data_points` | ✅ **Compatible** |

**Key Differences:**

1. **User Authentication**: Frontend uses Manus OAuth (`openId`, `loginMethod`), backend uses JWT (`password_hash`)
2. **Naming Convention**: Frontend uses camelCase, backend uses snake_case
3. **Database**: Frontend configured for MySQL/TiDB, backend uses PostgreSQL

---

## 4. Required Changes for Backend Integration

To integrate the frontend with the existing FastAPI backend, the following changes are required:

### 4.1 Authentication Integration

**Current State:**

- Frontend uses Manus OAuth with session cookies
- Backend uses FastAPI JWT authentication

**Required Changes:**

**File:** `client/src/_core/hooks/useAuth.ts`

***Change 1: Update authentication hook to call backend login endpoint**

```typescript
// Current implementation uses tRPC
const { data: user, isLoading, error } = trpc.auth.me.useQuery();

// New implementation should call backend REST API
const { data: user, isLoading, error } = useQuery({
  queryKey: ['auth', 'me'],
  queryFn: async () => {
    const response = await fetch('http://localhost:8000/api/auth/me', {
      credentials: 'include',
      headers: {
        'Authorization': `Bearer ${localStorage.getItem('access_token')}`
      }
    });
    if (!response.ok) throw new Error('Not authenticated');
    return response.json();
  }
});
```

**File:** `client/src/const.ts`

***Change 2: Update login URL to point to backend**

```typescript
// Current
export function getLoginUrl(returnPath?: string): string {
  const state = encodeURIComponent(JSON.stringify({
    origin: window.location.origin,
    returnPath: returnPath ?? window.location.pathname,
  }));
  return `${import.meta.env.VITE_OAUTH_PORTAL_URL}?app_id=${import.meta.env.VITE_APP_ID}&state=${state}`;
}

// New - redirect to backend login page
export function getLoginUrl(returnPath?: string): string {
  return `/login?returnPath=${encodeURIComponent(returnPath ?? '/')}`;
}
```

**File:** `client/src/pages/Login.tsx` (NEW FILE)

***Change 3: Create login page component**

```typescript
import { useState } from 'react';
import { useLocation } from 'wouter';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { toast } from 'sonner';

export default function Login() {
  const [, setLocation] = useLocation();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const formData = new FormData();
      formData.append('username', email);
      formData.append('password', password);

      const response = await fetch('http://localhost:8000/api/auth/login', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        throw new Error('Login failed');
      }

      const data = await response.json();
      localStorage.setItem('access_token', data.access_token);
      localStorage.setItem('refresh_token', data.refresh_token);

      toast.success('Login successful!');
      setLocation('/');
    } catch (error) {
      toast.error('Invalid email or password');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full space-y-8 p-8 bg-white rounded-lg shadow">
        <h2 className="text-3xl font-bold text-center">Sign in to FTIAS</h2>
        <form onSubmit={handleLogin} className="space-y-6">
          <Input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
          <Input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Button type="submit" className="w-full" disabled={isLoading}>
            {isLoading ? 'Signing in...' : 'Sign in'}
          </Button>
        </form>
      </div>
    </div>
  );
}
```

### 4.2 API Adapter Layer

**File:** `client/src/lib/backendAdapter.ts` (NEW FILE)

**Purpose:** Create an adapter layer to translate tRPC calls to REST API calls

```typescript
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

// Configure axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Add response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        const refreshToken = localStorage.getItem('refresh_token');
        const response = await axios.post(`${API_BASE_URL}/auth/refresh`, {
          refresh_token: refreshToken,
        });

        const { access_token } = response.data;
        localStorage.setItem('access_token', access_token);

        originalRequest.headers.Authorization = `Bearer ${access_token}`;
        return api(originalRequest);
      } catch (refreshError) {
        localStorage.removeItem('access_token');
        localStorage.removeItem('refresh_token');
        window.location.href = '/login';
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// Flight Tests API
export const flightTestsApi = {
  list: () => api.get('/flight-tests/'),
  get: (id: number) => api.get(`/flight-tests/${id}`),
  create: (data: any) => api.post('/flight-tests/', data),
  update: (id: number, data: any) => api.put(`/flight-tests/${id}`, data),
  delete: (id: number) => api.delete(`/flight-tests/${id}`),
  uploadCSV: (id: number, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post(`/flight-tests/${id}/upload-csv`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getDataPoints: (id: number, params?: any) =>
    api.get(`/flight-tests/${id}/data-points`, { params }),
};

// Parameters API
export const parametersApi = {
  list: () => api.get('/parameters/'),
  get: (id: number) => api.get(`/parameters/${id}`),
  create: (data: any) => api.post('/parameters/', data),
  update: (id: number, data: any) => api.put(`/parameters/${id}`, data),
  delete: (id: number) => api.delete(`/parameters/${id}`),
  uploadExcel: (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/parameters/upload-excel', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
};

// Users API
export const usersApi = {
  me: () => api.get('/users/me'),
  update: (data: any) => api.put('/users/me', data),
};

export default api;
```

### 4.3 Update Page Components

**File:** `client/src/pages/Home.tsx`

**Change:** Replace tRPC calls with backend adapter

```typescript
// Before
const { data: flightTests, isLoading } = trpc.flightTests.list.useQuery();

// After
import { useQuery } from '@tanstack/react-query';
import { flightTestsApi } from '@/lib/backendAdapter';

const { data: flightTests, isLoading } = useQuery({
  queryKey: ['flightTests'],
  queryFn: async () => {
    const response = await flightTestsApi.list();
    return response.data;
  },
});
```

**File:** `client/src/pages/Upload.tsx`

**Change:** Update file upload to use backend adapter

```typescript
// Before
const uploadCSV = trpc.flightTests.uploadCSV.useMutation();

// After
import { useMutation } from '@tanstack/react-query';
import { flightTestsApi } from '@/lib/backendAdapter';

const uploadCSV = useMutation({
  mutationFn: async ({ flightTestId, file }: { flightTestId: number; file: File }) => {
    const response = await flightTestsApi.uploadCSV(flightTestId, file);
    return response.data;
  },
  onSuccess: () => {
    toast.success('File uploaded successfully!');
  },
  onError: () => {
    toast.error('Failed to upload file');
  },
});
```

### 4.4 Environment Configuration

**File:** `.env` (NEW FILE in frontend root)

**Purpose:** Configure backend API URL

```env
VITE_API_BASE_URL=http://localhost:8000/api
VITE_APP_TITLE=Flight Test Interactive Analysis Suite
```

**File:** `vite.config.ts`

**Change:** Add proxy configuration for development

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  resolve: {
    alias: {
      '@': '/client/src',
      '@shared': '/shared',
    },
  },
});
```

### 4.5 CORS Configuration (Backend)

**File:** `backend/app/main.py`

**Change:** Enable CORS for frontend origin

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## 5. Testing Requirements

After implementing the changes, the following tests should be performed:

### 5.1 Authentication Flow

- [ ] User can log in with email and password
- [ ] JWT token is stored in localStorage
- [ ] Token is included in API requests
- [ ] Token refresh works when access token expires
- [ ] User is redirected to login when unauthorized
- [ ] Logout clears tokens and redirects to login

### 5.2 Flight Test Management

- [ ] Flight test list displays correctly
- [ ] Search and filtering work
- [ ] Create new flight test
- [ ] View flight test details
- [ ] Update flight test information
- [ ] Delete flight test

### 5.3 File Upload

- [ ] CSV file upload works
- [ ] Excel file upload works
- [ ] File validation shows errors for invalid files
- [ ] Upload progress is displayed
- [ ] Success/error toasts appear

### 5.4 Data Visualization

- [ ] Charts load with flight test data
- [ ] Parameter selection updates chart
- [ ] Zoom and pan work correctly
- [ ] Data statistics display accurately

---

## 6. Deployment Considerations

### 6.1 Environment Variables

The following environment variables need to be configured for production:

```env
# Frontend (.env)
VITE_API_BASE_URL=https://api.ftias.com/api
VITE_APP_TITLE=Flight Test Interactive Analysis Suite

# Backend (.env)
DATABASE_URL=postgresql://user:password@localhost:5432/ftias_db
JWT_SECRET=your-secret-key-here
CORS_ORIGINS=https://ftias.com
```

### 6.2 Build Process

**Frontend Build:**

```bash
cd frontend
pnpm install
pnpm build
```

**Output:** `frontend/dist/` directory containing static files

### 6.3 Docker Configuration

The frontend Dockerfile needs to be updated to use the new build:

**File:** `docker/frontend.Dockerfile`

```dockerfile
FROM node:22-alpine AS builder

WORKDIR /app

# Copy package files
COPY frontend/package.json frontend/pnpm-lock.yaml ./

# Install dependencies
RUN npm install -g pnpm && pnpm install --frozen-lockfile

# Copy source code
COPY frontend/ ./

# Build the application
RUN pnpm build

# Production stage
FROM nginx:alpine

# Copy built files
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

---

## 7. Summary of Required Changes

The following table summarizes all required changes:

| Category | File | Change Type | Priority |
 |----------|------|-------------|----------|
| **Authentication** | `client/src/_core/hooks/useAuth.ts` | Modify | 🔴 High |
| **Authentication** | `client/src/const.ts` | Modify | 🔴 High |
| **Authentication** | `client/src/pages/Login.tsx` | Create | 🔴 High |
| **API Layer** | `client/src/lib/backendAdapter.ts` | Create | 🔴 High |
| **Pages** | `client/src/pages/Home.tsx` | Modify | 🔴 High |
| **Pages** | `client/src/pages/Upload.tsx` | Modify | 🟡 Medium |
| **Pages** | `client/src/pages/Parameters.tsx` | Modify | 🟡 Medium |
| **Pages** | `client/src/pages/FlightTestDetail.tsx` | Modify | 🟡 Medium |
| **Configuration** | `.env` | Create | 🔴 High |
| **Configuration** | `vite.config.ts` | Modify | 🔴 High |
| **Backend** | `backend/app/main.py` | Modify (CORS) | 🔴 High |
| **Docker** | `docker/frontend.Dockerfile` | Modify | 🟢 Low |

---

## 8. Next Steps

**Immediate Actions (Today):**

1. Create the backend adapter file (`client/src/lib/backendAdapter.ts`)
2. Create the login page component (`client/src/pages/Login.tsx`)
3. Update authentication hook (`client/src/_core/hooks/useAuth.ts`)
4. Enable CORS in backend (`backend/app/main.py`)
5. Test authentication flow end-to-end

**Short-term Actions (This Week):**

1. Update all page components to use backend adapter
2. Test file upload functionality
3. Test data visualization with real backend data
4. Implement error handling for API failures
5. Add loading states and skeleton screens

**Long-term Actions (Next Sprint):**

1. Implement user registration flow
2. Add role-based access control
3. Optimize performance (code splitting, lazy loading)
4. Add comprehensive error logging
5. Prepare for production deployment

---

## Conclusion

The FTIAS frontend is well-architected and feature-complete from a UI perspective. The primary work required is integrating it with the existing FastAPI backend by creating an adapter layer and updating the authentication flow. The changes are straightforward and can be implemented incrementally, allowing for testing at each step.

The recommended approach is to start with authentication integration, then gradually update each page component to use the backend adapter. This allows for continuous testing and validation throughout the integration process.

---

**Document Status:** ✅ Complete
**Last Updated:** February 10, 2026
**Next Review:** After backend integration is complete
