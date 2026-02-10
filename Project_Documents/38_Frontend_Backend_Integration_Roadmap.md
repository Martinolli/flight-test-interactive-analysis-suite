# Frontend-Backend Integration Roadmap

**Document Number:** 36  
**Date:** February 10, 2026  
**Author:** Manus AI  
**Project:** Flight Test Interactive Analysis Suite (FTIAS)  
**Repository:** https://github.com/Martinolli/flight-test-interactive-analysis-suite

---

## Executive Summary

This document provides a comprehensive roadmap for integrating the FTIAS React frontend with the FastAPI backend. The integration requires replacing Manus OAuth with backend JWT authentication, creating an adapter layer to bridge tRPC and REST API, and connecting all frontend pages to backend endpoints.

**Current Status:**
- ✅ Backend fully functional (localhost:8000)
- ✅ Frontend UI rendering (localhost:3000)
- ⚠️ Frontend uses Manus OAuth (needs replacement)
- ⚠️ tRPC client needs adapter to call REST API

**Integration Strategy:** Create an adapter layer that translates tRPC procedure calls to REST API requests without modifying the backend.

---

## 1. Integration Overview

The integration process involves four major components that must work together seamlessly.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    React Frontend (Port 3000)                │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Dashboard   │  │   Upload     │  │   Parameters     │  │
│  │    Page      │  │    Page      │  │      Page        │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │             │
│         └─────────────────┼────────────────────┘             │
│                           │                                  │
│                    ┌──────▼───────┐                          │
│                    │  tRPC Client │                          │
│                    └──────┬───────┘                          │
│                           │                                  │
│                    ┌──────▼───────────────┐                  │
│                    │   Adapter Layer      │                  │
│                    │  (tRPC → REST)       │                  │
│                    └──────┬───────────────┘                  │
│                           │                                  │
└───────────────────────────┼──────────────────────────────────┘
                            │ HTTP Requests
                            │ (Authorization: Bearer <token>)
                            │
┌───────────────────────────▼──────────────────────────────────┐
│                  FastAPI Backend (Port 8000)                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │     Auth     │  │ Flight Tests │  │   Parameters     │  │
│  │   Router     │  │    Router    │  │     Router       │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
│         │                 │                    │             │
│         └─────────────────┼────────────────────┘             │
│                           │                                  │
│                    ┌──────▼───────┐                          │
│                    │  SQLAlchemy  │                          │
│                    │     ORM      │                          │
│                    └──────┬───────┘                          │
└───────────────────────────┼──────────────────────────────────┘
                            │
                    ┌───────▼────────┐
                    │   PostgreSQL   │
                    │    Database    │
                    └────────────────┘
```

### Integration Components

**1. Authentication System**
- Replace Manus OAuth with backend JWT authentication
- Implement login/logout flows
- Store and manage JWT tokens
- Add Authorization headers to all requests

**2. API Adapter Layer**
- Create bridge between tRPC and REST API
- Translate procedure calls to HTTP requests
- Handle request/response transformations
- Manage error handling

**3. Data Flow Integration**
- Connect frontend pages to backend endpoints
- Implement CRUD operations for flight tests
- Implement file upload functionality
- Implement data visualization queries

**4. Type Safety**
- Define TypeScript interfaces matching backend schemas
- Ensure type safety across frontend-backend boundary
- Handle snake_case to camelCase conversions

---

## 2. Phase-by-Phase Integration Plan

The integration is divided into six phases, each building on the previous one.

### Phase 1: Authentication Integration (Priority: Critical)

**Objective:** Replace Manus OAuth with backend JWT authentication system.

**Duration:** 2-3 hours

**Tasks:**

**1.1 Create Authentication Types**

Create `frontend/client/src/types/auth.ts`:
```typescript
export interface LoginRequest {
  username: string;  // Email or username
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
  id: number;
  email: string;
  username: string;
  full_name: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at: string | null;
}
```

**1.2 Create Authentication Service**

Create `frontend/client/src/services/auth.ts`:
```typescript
const API_BASE_URL = 'http://localhost:8000';

export class AuthService {
  static async login(email: string, password: string): Promise<TokenResponse> {
    const formData = new FormData();
    formData.append('username', email);
    formData.append('password', password);
    
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error('Login failed');
    }
    
    const data = await response.json();
    
    // Store tokens
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('refresh_token', data.refresh_token);
    localStorage.setItem('token_expiry', 
      String(Date.now() + data.expires_in * 1000));
    
    return data;
  }
  
  static async logout(): Promise<void> {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('token_expiry');
  }
  
  static async refreshToken(): Promise<TokenResponse> {
    const refreshToken = localStorage.getItem('refresh_token');
    
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }
    
    const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    
    if (!response.ok) {
      throw new Error('Token refresh failed');
    }
    
    const data = await response.json();
    
    // Update tokens
    localStorage.setItem('access_token', data.access_token);
    localStorage.setItem('token_expiry', 
      String(Date.now() + data.expires_in * 1000));
    
    return data;
  }
  
  static async getCurrentUser(): Promise<User> {
    const token = this.getAccessToken();
    
    if (!token) {
      throw new Error('No access token');
    }
    
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });
    
    if (!response.ok) {
      throw new Error('Failed to get current user');
    }
    
    return response.json();
  }
  
  static getAccessToken(): string | null {
    const token = localStorage.getItem('access_token');
    const expiry = localStorage.getItem('token_expiry');
    
    if (!token || !expiry) {
      return null;
    }
    
    // Check if token is expired
    if (Date.now() >= parseInt(expiry)) {
      return null;
    }
    
    return token;
  }
  
  static isAuthenticated(): boolean {
    return this.getAccessToken() !== null;
  }
}
```

**1.3 Create Auth Context**

Update `frontend/client/src/contexts/AuthContext.tsx`:
```typescript
import React, { createContext, useContext, useEffect, useState } from 'react';
import { AuthService } from '@/services/auth';
import type { User } from '@/types/auth';

interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  
  useEffect(() => {
    // Check if user is already logged in
    const loadUser = async () => {
      if (AuthService.isAuthenticated()) {
        try {
          const currentUser = await AuthService.getCurrentUser();
          setUser(currentUser);
        } catch (error) {
          console.error('Failed to load user:', error);
          await AuthService.logout();
        }
      }
      setIsLoading(false);
    };
    
    loadUser();
  }, []);
  
  const login = async (email: string, password: string) => {
    await AuthService.login(email, password);
    const currentUser = await AuthService.getCurrentUser();
    setUser(currentUser);
  };
  
  const logout = async () => {
    await AuthService.logout();
    setUser(null);
  };
  
  return (
    <AuthContext.Provider 
      value={{ 
        user, 
        isAuthenticated: !!user, 
        isLoading, 
        login, 
        logout 
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
```

**1.4 Create Login Page**

Create `frontend/client/src/pages/Login.tsx`:
```typescript
import { useState } from 'react';
import { useNavigate } from 'wouter';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { login } = useAuth();
  const [, navigate] = useNavigate();
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    
    try {
      await login(email, password);
      navigate('/');
    } catch (err) {
      setError('Invalid email or password');
    } finally {
      setIsLoading(false);
    }
  };
  
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Sign In</CardTitle>
          <CardDescription>
            Enter your credentials to access FTIAS
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="block text-sm font-medium mb-2">
                Email
              </label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                placeholder="engineer@example.com"
              />
            </div>
            
            <div>
              <label htmlFor="password" className="block text-sm font-medium mb-2">
                Password
              </label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                placeholder="••••••••"
              />
            </div>
            
            {error && (
              <div className="text-sm text-red-600">
                {error}
              </div>
            )}
            
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? 'Signing in...' : 'Sign In'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

**1.5 Update App.tsx**

Update routing to use new authentication:
```typescript
import { Route, Switch, Redirect } from 'wouter';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import Login from '@/pages/Login';
import Home from '@/pages/Home';
import Upload from '@/pages/Upload';
import Parameters from '@/pages/Parameters';
import Profile from '@/pages/Profile';

function ProtectedRoute({ component: Component, ...rest }: any) {
  const { isAuthenticated, isLoading } = useAuth();
  
  if (isLoading) {
    return <div>Loading...</div>;
  }
  
  return isAuthenticated ? <Component {...rest} /> : <Redirect to="/login" />;
}

function App() {
  return (
    <AuthProvider>
      <Switch>
        <Route path="/login" component={Login} />
        <Route path="/">
          {() => <ProtectedRoute component={Home} />}
        </Route>
        <Route path="/upload">
          {() => <ProtectedRoute component={Upload} />}
        </Route>
        <Route path="/parameters">
          {() => <ProtectedRoute component={Parameters} />}
        </Route>
        <Route path="/profile">
          {() => <ProtectedRoute component={Profile} />}
        </Route>
      </Switch>
    </AuthProvider>
  );
}

export default App;
```

**Testing Phase 1:**
1. Start backend: `cd backend && uvicorn app.main:app --reload`
2. Start frontend: `cd frontend && pnpm dev`
3. Navigate to `http://localhost:3000`
4. Should redirect to login page
5. Login with test credentials
6. Should redirect to dashboard

---

### Phase 2: API Adapter Layer (Priority: Critical)

**Objective:** Create adapter layer to translate tRPC calls to REST API requests.

**Duration:** 3-4 hours

**Tasks:**

**2.1 Create API Client**

Create `frontend/client/src/services/api.ts`:
```typescript
import { AuthService } from './auth';

const API_BASE_URL = 'http://localhost:8000';

export class ApiClient {
  private static async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = AuthService.getAccessToken();
    
    const headers: HeadersInit = {
      ...options.headers,
    };
    
    // Add auth header if token exists
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    // Add content-type for JSON requests
    if (options.body && typeof options.body === 'string') {
      headers['Content-Type'] = 'application/json';
    }
    
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });
    
    // Handle 401 Unauthorized - token expired
    if (response.status === 401) {
      try {
        // Try to refresh token
        await AuthService.refreshToken();
        // Retry request with new token
        return this.request<T>(endpoint, options);
      } catch (error) {
        // Refresh failed, logout user
        await AuthService.logout();
        window.location.href = '/login';
        throw new Error('Session expired');
      }
    }
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Request failed');
    }
    
    return response.json();
  }
  
  static async get<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'GET' });
  }
  
  static async post<T>(endpoint: string, data?: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'POST',
      body: data ? JSON.stringify(data) : undefined,
    });
  }
  
  static async put<T>(endpoint: string, data: any): Promise<T> {
    return this.request<T>(endpoint, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }
  
  static async delete<T>(endpoint: string): Promise<T> {
    return this.request<T>(endpoint, { method: 'DELETE' });
  }
  
  static async uploadFile<T>(endpoint: string, file: File): Promise<T> {
    const token = AuthService.getAccessToken();
    const formData = new FormData();
    formData.append('file', file);
    
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      throw new Error(error.detail || 'Upload failed');
    }
    
    return response.json();
  }
}
```

**2.2 Create Type Definitions**

Create `frontend/client/src/types/api.ts`:
```typescript
// Flight Test Types
export interface FlightTest {
  id: number;
  test_name: string;
  aircraft_type: string | null;
  test_date: string | null;
  duration_seconds: number | null;
  description: string | null;
  created_by_id: number;
  created_at: string;
  updated_at: string | null;
}

export interface CreateFlightTestRequest {
  test_name: string;
  aircraft_type?: string;
  test_date?: string;
  duration_seconds?: number;
  description?: string;
}

export interface UpdateFlightTestRequest {
  test_name?: string;
  aircraft_type?: string;
  test_date?: string;
  duration_seconds?: number;
  description?: string;
}

// Parameter Types
export interface Parameter {
  id: number;
  name: string;
  description: string | null;
  unit: string | null;
  system: string | null;
  category: string | null;
  min_value: number | null;
  max_value: number | null;
  created_at: string;
  updated_at: string | null;
}

export interface CreateParameterRequest {
  name: string;
  description?: string;
  unit?: string;
  system?: string;
  category?: string;
  min_value?: number;
  max_value?: number;
}

export interface UpdateParameterRequest {
  name?: string;
  description?: string;
  unit?: string;
  system?: string;
  category?: string;
  min_value?: number;
  max_value?: number;
}

// Data Point Types
export interface DataPoint {
  id: number;
  flight_test_id: number;
  parameter_id: number;
  timestamp: string;
  value: number;
  created_at: string;
}

export interface DataPointsQuery {
  skip?: number;
  limit?: number;
  parameter_id?: number;
}

// User Types
export interface UpdateUserRequest {
  email?: string;
  username?: string;
  full_name?: string;
  password?: string;
}
```

**2.3 Create tRPC Adapter**

Update `frontend/server/routers.ts` to use API client:
```typescript
import { publicProcedure, protectedProcedure, router } from "./_core/trpc";
import { z } from "zod";
import { ApiClient } from "../client/src/services/api";

export const appRouter = router({
  // Flight Tests
  flightTests: router({
    list: protectedProcedure.query(async () => {
      return ApiClient.get<FlightTest[]>('/api/flight-tests/');
    }),
    
    get: protectedProcedure
      .input(z.object({ id: z.number() }))
      .query(async ({ input }) => {
        return ApiClient.get<FlightTest>(`/api/flight-tests/${input.id}`);
      }),
    
    create: protectedProcedure
      .input(z.object({
        test_name: z.string(),
        aircraft_type: z.string().optional(),
        test_date: z.string().optional(),
        duration_seconds: z.number().optional(),
        description: z.string().optional(),
      }))
      .mutation(async ({ input }) => {
        return ApiClient.post<FlightTest>('/api/flight-tests/', input);
      }),
    
    update: protectedProcedure
      .input(z.object({
        id: z.number(),
        test_name: z.string().optional(),
        aircraft_type: z.string().optional(),
        test_date: z.string().optional(),
        duration_seconds: z.number().optional(),
        description: z.string().optional(),
      }))
      .mutation(async ({ input }) => {
        const { id, ...data } = input;
        return ApiClient.put<FlightTest>(`/api/flight-tests/${id}`, data);
      }),
    
    delete: protectedProcedure
      .input(z.object({ id: z.number() }))
      .mutation(async ({ input }) => {
        return ApiClient.delete(`/api/flight-tests/${input.id}`);
      }),
    
    uploadCsv: protectedProcedure
      .input(z.object({
        id: z.number(),
        file: z.instanceof(File),
      }))
      .mutation(async ({ input }) => {
        return ApiClient.uploadFile(
          `/api/flight-tests/${input.id}/upload-csv`,
          input.file
        );
      }),
    
    getDataPoints: protectedProcedure
      .input(z.object({
        id: z.number(),
        skip: z.number().optional(),
        limit: z.number().optional(),
        parameter_id: z.number().optional(),
      }))
      .query(async ({ input }) => {
        const { id, ...params } = input;
        const queryString = new URLSearchParams(
          Object.entries(params)
            .filter(([_, v]) => v !== undefined)
            .map(([k, v]) => [k, String(v)])
        ).toString();
        return ApiClient.get<DataPoint[]>(
          `/api/flight-tests/${id}/data-points?${queryString}`
        );
      }),
  }),
  
  // Parameters
  parameters: router({
    list: protectedProcedure.query(async () => {
      return ApiClient.get<Parameter[]>('/api/parameters/');
    }),
    
    get: protectedProcedure
      .input(z.object({ id: z.number() }))
      .query(async ({ input }) => {
        return ApiClient.get<Parameter>(`/api/parameters/${input.id}`);
      }),
    
    create: protectedProcedure
      .input(z.object({
        name: z.string(),
        description: z.string().optional(),
        unit: z.string().optional(),
        system: z.string().optional(),
        category: z.string().optional(),
        min_value: z.number().optional(),
        max_value: z.number().optional(),
      }))
      .mutation(async ({ input }) => {
        return ApiClient.post<Parameter>('/api/parameters/', input);
      }),
    
    update: protectedProcedure
      .input(z.object({
        id: z.number(),
        name: z.string().optional(),
        description: z.string().optional(),
        unit: z.string().optional(),
        system: z.string().optional(),
        category: z.string().optional(),
        min_value: z.number().optional(),
        max_value: z.number().optional(),
      }))
      .mutation(async ({ input }) => {
        const { id, ...data } = input;
        return ApiClient.put<Parameter>(`/api/parameters/${id}`, data);
      }),
    
    delete: protectedProcedure
      .input(z.object({ id: z.number() }))
      .mutation(async ({ input }) => {
        return ApiClient.delete(`/api/parameters/${input.id}`);
      }),
    
    uploadExcel: protectedProcedure
      .input(z.object({ file: z.instanceof(File) }))
      .mutation(async ({ input }) => {
        return ApiClient.uploadFile('/api/parameters/upload-excel', input.file);
      }),
  }),
  
  // User Profile
  user: router({
    me: protectedProcedure.query(async () => {
      return ApiClient.get<User>('/api/users/me');
    }),
    
    update: protectedProcedure
      .input(z.object({
        email: z.string().optional(),
        username: z.string().optional(),
        full_name: z.string().optional(),
        password: z.string().optional(),
      }))
      .mutation(async ({ input }) => {
        return ApiClient.put<User>('/api/users/me', input);
      }),
  }),
});

export type AppRouter = typeof appRouter;
```

**Testing Phase 2:**
1. Test tRPC procedures call backend API correctly
2. Verify authentication headers are included
3. Test error handling (401, 404, 500)
4. Test token refresh flow

---

### Phase 3: Dashboard Integration (Priority: High)

**Objective:** Connect dashboard page to backend flight test endpoints.

**Duration:** 2-3 hours

**Tasks:**

**3.1 Update Dashboard Page**

Update `frontend/client/src/pages/Home.tsx`:
```typescript
import { useState } from 'react';
import { trpc } from '@/lib/trpc';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useNavigate } from 'wouter';

export default function Home() {
  const [, navigate] = useNavigate();
  const { data: flightTests, isLoading, refetch } = trpc.flightTests.list.useQuery();
  const deleteMutation = trpc.flightTests.delete.useMutation({
    onSuccess: () => {
      refetch();
    },
  });
  
  if (isLoading) {
    return <div>Loading flight tests...</div>;
  }
  
  return (
    <div className="container mx-auto py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Flight Tests</h1>
        <Button onClick={() => navigate('/upload')}>
          New Flight Test
        </Button>
      </div>
      
      <div className="grid gap-4">
        {flightTests?.map((test) => (
          <Card key={test.id}>
            <CardHeader>
              <CardTitle>{test.test_name}</CardTitle>
              <CardDescription>
                {test.aircraft_type && `Aircraft: ${test.aircraft_type}`}
                {test.test_date && ` • Date: ${new Date(test.test_date).toLocaleDateString()}`}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <p className="text-sm text-muted-foreground mb-4">
                {test.description || 'No description'}
              </p>
              <div className="flex gap-2">
                <Button 
                  variant="outline" 
                  onClick={() => navigate(`/flight-test/${test.id}`)}
                >
                  View Details
                </Button>
                <Button 
                  variant="destructive" 
                  onClick={() => deleteMutation.mutate({ id: test.id })}
                  disabled={deleteMutation.isLoading}
                >
                  Delete
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
        
        {flightTests?.length === 0 && (
          <Card>
            <CardContent className="py-8 text-center">
              <p className="text-muted-foreground">No flight tests yet</p>
              <Button 
                className="mt-4" 
                onClick={() => navigate('/upload')}
              >
                Create Your First Flight Test
              </Button>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
```

**Testing Phase 3:**
1. Navigate to dashboard
2. Verify flight tests are loaded from backend
3. Test delete functionality
4. Test navigation to detail page

---

### Phase 4: Upload Integration (Priority: High)

**Objective:** Connect upload page to backend CSV upload endpoint.

**Duration:** 2-3 hours

**Tasks:**

**4.1 Update Upload Page**

Update `frontend/client/src/pages/Upload.tsx`:
```typescript
import { useState } from 'react';
import { trpc } from '@/lib/trpc';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { useNavigate } from 'wouter';

export default function Upload() {
  const [, navigate] = useNavigate();
  const [testName, setTestName] = useState('');
  const [aircraftType, setAircraftType] = useState('');
  const [description, setDescription] = useState('');
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  
  const createMutation = trpc.flightTests.create.useMutation();
  const uploadMutation = trpc.flightTests.uploadCsv.useMutation();
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsUploading(true);
    
    try {
      // Create flight test
      const flightTest = await createMutation.mutateAsync({
        test_name: testName,
        aircraft_type: aircraftType || undefined,
        description: description || undefined,
      });
      
      // Upload CSV if provided
      if (csvFile) {
        await uploadMutation.mutateAsync({
          id: flightTest.id,
          file: csvFile,
        });
      }
      
      // Navigate to dashboard
      navigate('/');
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed. Please try again.');
    } finally {
      setIsUploading(false);
    }
  };
  
  return (
    <div className="container mx-auto py-8 max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle>Create Flight Test</CardTitle>
          <CardDescription>
            Upload a new flight test with optional CSV data
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Test Name *
              </label>
              <Input
                value={testName}
                onChange={(e) => setTestName(e.target.value)}
                required
                placeholder="F-16 High-G Maneuver Test"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-2">
                Aircraft Type
              </label>
              <Input
                value={aircraftType}
                onChange={(e) => setAircraftType(e.target.value)}
                placeholder="F-16C"
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-2">
                Description
              </label>
              <textarea
                className="w-full min-h-[100px] rounded-md border border-input bg-background px-3 py-2"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Test description..."
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-2">
                CSV Data File (Optional)
              </label>
              <Input
                type="file"
                accept=".csv"
                onChange={(e) => setCsvFile(e.target.files?.[0] || null)}
              />
              <p className="text-xs text-muted-foreground mt-1">
                CSV format: First column = timestamp, remaining columns = parameters
              </p>
            </div>
            
            <div className="flex gap-2">
              <Button type="submit" disabled={isUploading}>
                {isUploading ? 'Creating...' : 'Create Flight Test'}
              </Button>
              <Button 
                type="button" 
                variant="outline" 
                onClick={() => navigate('/')}
              >
                Cancel
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

**Testing Phase 4:**
1. Navigate to upload page
2. Create flight test without CSV
3. Create flight test with CSV
4. Verify data is uploaded to backend
5. Verify redirect to dashboard

---

### Phase 5: Parameters Integration (Priority: Medium)

**Objective:** Connect parameters page to backend parameter endpoints.

**Duration:** 2 hours

**Tasks:**

**5.1 Update Parameters Page**

Update `frontend/client/src/pages/Parameters.tsx`:
```typescript
import { useState } from 'react';
import { trpc } from '@/lib/trpc';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';

export default function Parameters() {
  const { data: parameters, isLoading, refetch } = trpc.parameters.list.useQuery();
  const [excelFile, setExcelFile] = useState<File | null>(null);
  const uploadMutation = trpc.parameters.uploadExcel.useMutation({
    onSuccess: () => {
      refetch();
      setExcelFile(null);
    },
  });
  
  const handleUpload = async () => {
    if (!excelFile) return;
    
    try {
      await uploadMutation.mutateAsync({ file: excelFile });
      alert('Parameters uploaded successfully');
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Upload failed. Please try again.');
    }
  };
  
  if (isLoading) {
    return <div>Loading parameters...</div>;
  }
  
  return (
    <div className="container mx-auto py-8">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold">Parameters</h1>
      </div>
      
      <Card className="mb-8">
        <CardHeader>
          <CardTitle>Upload Parameters from Excel</CardTitle>
          <CardDescription>
            Upload an Excel file with parameter definitions
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              type="file"
              accept=".xlsx,.xls"
              onChange={(e) => setExcelFile(e.target.files?.[0] || null)}
            />
            <Button 
              onClick={handleUpload} 
              disabled={!excelFile || uploadMutation.isLoading}
            >
              {uploadMutation.isLoading ? 'Uploading...' : 'Upload'}
            </Button>
          </div>
        </CardContent>
      </Card>
      
      <Card>
        <CardHeader>
          <CardTitle>All Parameters ({parameters?.length || 0})</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Unit</TableHead>
                <TableHead>System</TableHead>
                <TableHead>Category</TableHead>
                <TableHead>Range</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {parameters?.map((param) => (
                <TableRow key={param.id}>
                  <TableCell className="font-medium">{param.name}</TableCell>
                  <TableCell>{param.unit || '-'}</TableCell>
                  <TableCell>{param.system || '-'}</TableCell>
                  <TableCell>{param.category || '-'}</TableCell>
                  <TableCell>
                    {param.min_value !== null && param.max_value !== null
                      ? `${param.min_value} - ${param.max_value}`
                      : '-'}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
```

**Testing Phase 5:**
1. Navigate to parameters page
2. Verify parameters are loaded from backend
3. Test Excel upload functionality
4. Verify new parameters appear in table

---

### Phase 6: Profile Integration (Priority: Low)

**Objective:** Connect profile page to backend user endpoints.

**Duration:** 1 hour

**Tasks:**

**6.1 Update Profile Page**

Update `frontend/client/src/pages/Profile.tsx`:
```typescript
import { useState, useEffect } from 'react';
import { trpc } from '@/lib/trpc';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function Profile() {
  const { user, logout } = useAuth();
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  
  const updateMutation = trpc.user.update.useMutation({
    onSuccess: () => {
      alert('Profile updated successfully');
    },
  });
  
  useEffect(() => {
    if (user) {
      setEmail(user.email);
      setUsername(user.username);
      setFullName(user.full_name || '');
    }
  }, [user]);
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    try {
      await updateMutation.mutateAsync({
        email,
        username,
        full_name: fullName || undefined,
      });
    } catch (error) {
      console.error('Update failed:', error);
      alert('Update failed. Please try again.');
    }
  };
  
  return (
    <div className="container mx-auto py-8 max-w-2xl">
      <Card>
        <CardHeader>
          <CardTitle>Profile Settings</CardTitle>
          <CardDescription>
            Manage your account information
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-2">
                Email
              </label>
              <Input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-2">
                Username
              </label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            
            <div>
              <label className="block text-sm font-medium mb-2">
                Full Name
              </label>
              <Input
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
              />
            </div>
            
            <div className="flex gap-2">
              <Button type="submit" disabled={updateMutation.isLoading}>
                {updateMutation.isLoading ? 'Saving...' : 'Save Changes'}
              </Button>
              <Button 
                type="button" 
                variant="destructive" 
                onClick={logout}
              >
                Logout
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

**Testing Phase 6:**
1. Navigate to profile page
2. Verify user data is loaded
3. Test profile update
4. Test logout functionality

---

## 3. Testing Strategy

Comprehensive testing is required to ensure integration works correctly.

### 3.1 Unit Testing

**Frontend Tests:**
- Test authentication service (login, logout, token refresh)
- Test API client (request handling, error handling)
- Test tRPC procedures

**Backend Tests:**
- Already complete (88% coverage)

### 3.2 Integration Testing

**End-to-End Tests:**
1. **Authentication Flow**
   - Login with valid credentials
   - Login with invalid credentials
   - Token expiration and refresh
   - Logout

2. **Flight Test Management**
   - Create flight test
   - List flight tests
   - View flight test details
   - Update flight test
   - Delete flight test
   - Upload CSV data

3. **Parameter Management**
   - List parameters
   - Upload Excel parameters
   - View parameter details

4. **User Profile**
   - View profile
   - Update profile

### 3.3 Manual Testing Checklist

- [ ] User can login with valid credentials
- [ ] User cannot login with invalid credentials
- [ ] User is redirected to login when not authenticated
- [ ] User can create flight test
- [ ] User can upload CSV file
- [ ] User can view flight test list
- [ ] User can delete flight test
- [ ] User can upload Excel parameters
- [ ] User can view parameter list
- [ ] User can update profile
- [ ] User can logout
- [ ] Token refresh works automatically
- [ ] Error messages are displayed correctly
- [ ] Loading states are shown during API calls

---

## 4. Deployment Guide

### 4.1 Local Development

**Start Backend:**
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Start Frontend:**
```bash
cd frontend
pnpm dev
```

**Access Application:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

### 4.2 Production Deployment

**Environment Variables:**

Backend `.env`:
```env
DATABASE_URL=postgresql://user:password@db-host:5432/ftias_db
JWT_SECRET=your-production-secret-min-32-chars
CORS_ORIGINS=https://ftias.com
DEBUG=False
```

Frontend `.env`:
```env
VITE_API_BASE_URL=https://api.ftias.com
```

**Docker Deployment:**

Update `docker-compose.yml`:
```yaml
version: '3.8'

services:
  backend:
    build:
      context: .
      dockerfile: docker/backend.Dockerfile
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - JWT_SECRET=${JWT_SECRET}
      - CORS_ORIGINS=https://ftias.com
    depends_on:
      - postgres
  
  frontend:
    build:
      context: .
      dockerfile: docker/frontend.Dockerfile
    ports:
      - "3000:3000"
    environment:
      - VITE_API_BASE_URL=https://api.ftias.com
  
  postgres:
    image: postgres:14
    environment:
      - POSTGRES_USER=${POSTGRES_USER}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

**Deploy:**
```bash
docker-compose up -d
```

---

## 5. Troubleshooting

### Common Issues

**Issue: CORS errors in browser console**
- **Cause:** Backend CORS configuration doesn't include frontend URL
- **Solution:** Update `CORS_ORIGINS` in backend `config.py`

**Issue: 401 Unauthorized errors**
- **Cause:** Missing or expired JWT token
- **Solution:** Check token storage, implement token refresh

**Issue: Token refresh loop**
- **Cause:** Refresh token is also expired
- **Solution:** Logout user and redirect to login

**Issue: CSV upload fails**
- **Cause:** File format doesn't match expected structure
- **Solution:** Add better error messages, validate file format

**Issue: Type errors in TypeScript**
- **Cause:** Backend response doesn't match frontend types
- **Solution:** Update type definitions to match backend schemas

---

## 6. Next Steps

After completing the integration, consider these enhancements:

**Short-term:**
1. Add data visualization charts for flight test data
2. Implement real-time data updates with WebSockets
3. Add export functionality (PDF reports, CSV exports)
4. Implement advanced search and filtering

**Medium-term:**
1. Add user roles and permissions
2. Implement data comparison between flight tests
3. Add automated analysis and anomaly detection
4. Implement data archiving

**Long-term:**
1. Add machine learning for predictive analysis
2. Implement collaborative features (comments, sharing)
3. Add mobile application
4. Implement advanced visualization (3D plots, animations)

---

## 7. Summary

This integration roadmap provides a comprehensive, step-by-step guide to connecting the FTIAS frontend with the backend API. The approach uses an adapter layer to bridge tRPC and REST API without modifying the backend, ensuring a clean separation of concerns.

**Key Milestones:**
1. ✅ Authentication integration (2-3 hours)
2. ✅ API adapter layer (3-4 hours)
3. ✅ Dashboard integration (2-3 hours)
4. ✅ Upload integration (2-3 hours)
5. ✅ Parameters integration (2 hours)
6. ✅ Profile integration (1 hour)

**Total Estimated Time:** 12-16 hours

**Success Criteria:**
- User can login with backend credentials
- User can create and manage flight tests
- User can upload CSV and Excel files
- User can view and manage parameters
- User can update profile
- All operations use backend API
- Error handling works correctly
- Token refresh works automatically

---

**Document Status:** ✅ Complete  
**Last Updated:** February 10, 2026  
**Ready for Implementation:** Yes
