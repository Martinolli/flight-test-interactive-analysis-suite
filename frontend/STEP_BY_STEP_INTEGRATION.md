# Step-by-Step Integration Guide - Connecting Frontend to Backend

This guide shows you **exactly** how to connect the Manus frontend to your existing FastAPI backend.

**Prerequisite:** Complete Part 1 (Local Development Setup) first.

---

## 🎯 What We're Doing

The frontend currently uses **tRPC** to talk to the backend, but your backend uses **REST API**. We'll create an "adapter" that translates between them - no backend changes needed!

---

## Part 2: Frontend-Backend Integration

### **Step 1: Create the API Adapter File**

1. Navigate to your frontend folder:
   ```bash
   cd flight-test-interactive-analysis-suite/frontend
   ```

2. Create a new file at this exact path:
   ```
   frontend/client/src/lib/backendAdapter.ts
   ```

3. Copy this **complete code** into `backendAdapter.ts`:

```typescript
import axios from 'axios';

// Create API client that talks to your FastAPI backend
const api = axios.create({
        baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add JWT token to all requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Adapter that makes tRPC calls work with your REST API
export const backendAdapter = {
  // Flight Tests API
  flightTests: {
    list: {
      useQuery: () => {
        const [data, setData] = useState<any[]>([]);
        const [isLoading, setIsLoading] = useState(true);
        const [error, setError] = useState<Error | null>(null);

        useEffect(() => {
          api.get('/api/flight-tests/')
            .then(res => {
              setData(res.data);
              setIsLoading(false);
            })
            .catch(err => {
              setError(err);
              setIsLoading(false);
            });
        }, []);

        return { data, isLoading, error };
      },
    },
    create: {
      useMutation: () => {
        return {
          mutateAsync: async (input: any) => {
            const { data } = await api.post('/api/flight-tests/', input);
            return data;
          },
        };
      },
    },
    getById: {
      useQuery: (params: { id: number }) => {
        const [data, setData] = useState<any>(null);
        const [isLoading, setIsLoading] = useState(true);
        const [error, setError] = useState<Error | null>(null);

        useEffect(() => {
          if (params.id) {
            api.get(`/api/flight-tests/${params.id}`)
              .then(res => {
                setData(res.data);
                setIsLoading(false);
              })
              .catch(err => {
                setError(err);
                setIsLoading(false);
              });
          }
        }, [params.id]);

        return { data, isLoading, error };
      },
    },
    update: {
      useMutation: () => {
        return {
          mutateAsync: async ({ id, ...input }: any) => {
            await api.put(`/api/flight-tests/${id}`, input);
            return { success: true };
          },
        };
      },
    },
    delete: {
      useMutation: () => {
        return {
          mutateAsync: async ({ id }: { id: number }) => {
            await api.delete(`/api/flight-tests/${id}`);
            return { success: true };
          },
        };
      },
    },
  },

  // Parameters API
  parameters: {
    list: {
      useQuery: () => {
        const [data, setData] = useState<any[]>([]);
        const [isLoading, setIsLoading] = useState(true);
        const [error, setError] = useState<Error | null>(null);

        useEffect(() => {
          api.get('/api/parameters/')
            .then(res => {
              setData(res.data);
              setIsLoading(false);
            })
            .catch(err => {
              setError(err);
              setIsLoading(false);
            });
        }, []);

        return { data, isLoading, error };
      },
    },
    create: {
      useMutation: () => {
        return {
          mutateAsync: async (input: any) => {
            const { data } = await api.post('/api/parameters/', input);
            return data;
          },
        };
      },
    },
  },

  // Data Points API
  dataPoints: {
    getByFlightTest: {
      useQuery: (params: { flightTestId: number }) => {
        const [data, setData] = useState<any[]>([]);
        const [isLoading, setIsLoading] = useState(true);
        const [error, setError] = useState<Error | null>(null);

        useEffect(() => {
          if (params.flightTestId) {
            api.get(`/api/flight-tests/${params.flightTestId}/data-points`)
              .then(res => {
                setData(res.data);
                setIsLoading(false);
              })
              .catch(err => {
                setError(err);
                setIsLoading(false);
              });
          }
        }, [params.flightTestId]);

        return { data, isLoading, error };
      },
    },
  },

  // Authentication API
  auth: {
    me: {
      useQuery: () => {
        const [data, setData] = useState<any>(null);
        const [isLoading, setIsLoading] = useState(true);
        const [error, setError] = useState<Error | null>(null);

        useEffect(() => {
          const token = localStorage.getItem('access_token');
          if (token) {
            api.get('/api/auth/me')
              .then(res => {
                setData(res.data);
                setIsLoading(false);
              })
              .catch(err => {
                setError(err);
                setIsLoading(false);
              });
          } else {
            setIsLoading(false);
          }
        }, []);

        return { data, isLoading, error };
      },
    },
    logout: {
      useMutation: () => {
        return {
          mutateAsync: async () => {
            localStorage.removeItem('access_token');
            return { success: true };
          },
        };
      },
    },
  },
};

// Import React hooks at the top
import { useState, useEffect } from 'react';
```

4. **Save the file**

---

### **Step 2: Update the tRPC Client File**

1. Open this file:
   ```
   frontend/client/src/lib/trpc.ts
   ```

2. **Replace all content** with this:

```typescript
// Import the backend adapter instead of tRPC
import { backendAdapter } from './backendAdapter';

// Export it as 'trpc' so existing code works without changes
export const trpc = backendAdapter;
```

3. **Save the file**

---

### **Step 3: Install Axios**

The adapter uses Axios to make HTTP requests. Install it:

```bash
cd frontend
pnpm add axios
```

---

### **Step 4: Update CORS in Your Backend**

Your backend needs to allow requests from the frontend.

1. Open this file:
   ```
   backend/app/main.py
   ```

2. Find the CORS middleware section (around line 20-30)

3. Make sure it looks like this:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Frontend development server
        "http://localhost:5173",  # Alternative Vite port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

4. **Save the file**

5. **Restart your backend** (press CTRL+C in the backend terminal, then run `uvicorn` again)

---

### **Step 5: Test the Integration**

1. Make sure both backend and frontend are running:
   - Backend: `http://localhost:8000`
   - Frontend: `http://localhost:3000`

2. Open your browser to `http://localhost:3000`

3. Try these tests:
   - Click "New Flight Test" button
   - Fill in the form and submit
   - Check if the flight test appears in the list
   - Click on a flight test to view details

---

## ✅ Verification Checklist

- [ ] Backend is running with CORS enabled
- [ ] Frontend is running
- [ ] No CORS errors in browser console (press F12 to check)
- [ ] Can create a new flight test
- [ ] Can see flight tests in the list
- [ ] Can click on a flight test to view details

---

## 🐛 Troubleshooting

### **Problem: "CORS policy" error in browser console**

**Solution:**
1. Check that your backend's `main.py` has the CORS middleware (Step 4)
2. Make sure `http://localhost:3000` is in the `allow_origins` list
3. Restart the backend after making changes

### **Problem: "Network Error" or "Failed to fetch"**

**Solution:**
1. Check that backend is running at `http://localhost:8000`
2. Test the backend directly: Open `http://localhost:8000/api/health` in your browser
3. Check the backend terminal for error messages

### **Problem: "401 Unauthorized" errors**

**Solution:**
1. The authentication system needs to be connected
2. For now, you can test without auth by temporarily removing the JWT token check in your backend
3. Or implement the login flow (see Step 6 below)

---

## 🔐 Step 6: Connect Authentication (Optional - Do Later)

The authentication system needs special handling. For now, you can:

**Option A: Test without authentication**
- Temporarily disable JWT requirements in your backend for testing

**Option B: Implement login flow**
- I can help you create a login page that works with your backend's `/api/auth/login` endpoint

**Which would you prefer?** Let me know and I'll provide exact instructions.

---

## 🎉 Success!

If you can create and view flight tests, congratulations! The frontend and backend are now connected.

---

## 📝 What We Did

1. ✅ Created an adapter that translates tRPC calls to REST API calls
2. ✅ Updated the tRPC client to use the adapter
3. ✅ Installed Axios for HTTP requests
4. ✅ Enabled CORS in the backend
5. ✅ Tested the integration

**Next Steps:**
- Connect the authentication system
- Test file uploads (CSV/Excel)
- Add more features as needed

---

## 🆘 Need Help?

If you encounter any issues:
1. Check the browser console (F12) for error messages
2. Check the backend terminal for error messages
3. Let me know the exact error message and I'll help you fix it!
