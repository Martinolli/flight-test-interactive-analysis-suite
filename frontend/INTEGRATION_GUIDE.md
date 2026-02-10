# Frontend-Backend Integration Guide

This guide explains how to integrate the Manus-created React frontend with your existing FastAPI backend.

---

## 🎯 Current Situation

- **Your Backend**: FastAPI with REST endpoints at `/api/flight-tests`, `/api/parameters`, etc.
- **Manus Frontend**: React app using tRPC for API communication
- **Challenge**: The frontend expects tRPC endpoints, but your backend provides REST endpoints

---

## 🔄 Integration Options

### **Option 1: Adapter Layer (Recommended - Fastest)**

Create an adapter that translates tRPC calls to REST API calls without modifying the backend.

#### **Implementation:**

1. Create `client/src/lib/backendAdapter.ts`:

```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
});

// Add JWT token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export const backendAdapter = {
  flightTests: {
    list: async () => {
      const { data } = await api.get('/api/flight-tests/');
      return data;
    },
    create: async (input: any) => {
      const { data } = await api.post('/api/flight-tests/', input);
      return data;
    },
    getById: async ({ id }: { id: number }) => {
      const { data } = await api.get(`/api/flight-tests/${id}`);
      return data;
    },
    update: async ({ id, ...input }: any) => {
      await api.put(`/api/flight-tests/${id}`, input);
      return { success: true };
    },
    delete: async ({ id }: { id: number }) => {
      await api.delete(`/api/flight-tests/${id}`);
      return { success: true };
    },
  },
  parameters: {
    list: async () => {
      const { data } = await api.get('/api/parameters/');
      return data;
    },
    create: async (input: any) => {
      const { data } = await api.post('/api/parameters/', input);
      return data;
    },
  },
  dataPoints: {
    getByFlightTest: async ({ flightTestId }: { flightTestId: number }) => {
      const { data } = await api.get(`/api/flight-tests/${flightTestId}/data-points`);
      return data;
    },
  },
  auth: {
    login: async (credentials: { username: string; password: string }) => {
      const formData = new FormData();
      formData.append('username', credentials.username);
      formData.append('password', credentials.password);

      const { data } = await api.post('/api/auth/login', formData);
      localStorage.setItem('access_token', data.access_token);
      return data;
    },
    me: async () => {
      const { data } = await api.get('/api/auth/me');
      return data;
    },
    logout: async () => {
      localStorage.removeItem('access_token');
      return { success: true };
    },
  },
};
```

   Update `client/src/lib/trpc.ts` to use the adapter:

```typescript
// Replace tRPC with the adapter
export const trpc = backendAdapter as any; // Type assertion for compatibility
```

---

### **Option 2: Add tRPC to Backend (Better Long-term)**

Add tRPC support to your FastAPI backend using `fastapi-trpc`.

#### *Implementation:*

1. Install tRPC for Python:

```bash
pip install fastapi-trpc
```

Create `backend/app/trpc_router.py`:

```python
from fastapi_trpc import TRPCRouter
from app.routers import flight_tests, parameters, auth

trpc_router = TRPCRouter()

# Register your existing routers
trpc_router.include_router(flight_tests.router)
trpc_router.include_router(parameters.router)
trpc_router.include_router(auth.router)
```

Update `backend/app/main.py`:

```python
from app.trpc_router import trpc_router

app.include_router(trpc_router, prefix="/api/trpc")
```

---

### **Option 3: Use Existing Backend As-Is**

Keep your FastAPI backend unchanged and update the frontend components to use REST API directly.

#### **Steps:**

1. Replace all `trpc.*` calls in components with direct API calls
2. Use React Query for data fetching and caching
3. Handle authentication with JWT tokens

---

## 🔐 Authentication Integration

Your backend uses JWT tokens. Update the frontend to work with your auth system:

1. **Login Flow:**

```typescript
// In Login component
const handleLogin = async (username: string, password: string) => {
  const formData = new FormData();
  formData.append('username', username);
  formData.append('password', password);

  const response = await fetch('http://localhost:8000/api/auth/login', {
    method: 'POST',
    body: formData,
  });

  const data = await response.json();
  localStorage.setItem('access_token', data.access_token);

  // Redirect to dashboard
  window.location.href = '/';
};
```

1. **Protected Routes:**

```typescript
// Add token to all API requests
const token = localStorage.getItem('access_token');
headers: {
  'Authorization': `Bearer ${token}`,
}
```

---

## 📁 File Upload Integration

Connect the frontend upload components to your backend endpoints:

```typescript
// In Upload.tsx
const handleCSVUpload = async (file: File, flightTestId: number) => {
  const formData = new FormData();
  formData.append('file', file);

  const token = localStorage.getItem('access_token');

  const response = await fetch(
    `http://localhost:8000/api/flight-tests/${flightTestId}/upload-csv`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
      },
      body: formData,
    }
  );

  if (response.ok) {
    toast.success('CSV uploaded successfully!');
  } else {
    toast.error('Upload failed');
  }
};
```

---

## 🧪 Testing the Integration

1. **Start Backend:**

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

1. **Start Frontend:**

```bash
cd frontend
pnpm dev
```

1. **Test Endpoints:**

- Login at `http://localhost:3000`
- Create a flight test
- Upload CSV data
- View charts and data

---

## 🚀 Deployment

Once integrated, deploy both:

1. **Backend**: Deploy FastAPI to your server (Railway, Render, etc.)
2. **Frontend**: Deploy React app to Vercel, Netlify, or your server
3. **Environment Variables**: Set `VITE_API_URL` to your production backend URL

---

## 💡 Recommendation

**I recommend Option 1 (Adapter Layer)** because:

- ✅ No backend changes required
- ✅ Fastest to implement
- ✅ Keeps your existing backend stable
- ✅ Can migrate to tRPC later if needed

Would you like me to help you implement the adapter layer?
