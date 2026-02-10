# Local Development Setup Guide

This guide explains how to run the Flight Test Interactive Analysis Suite locally on your machine, connecting the frontend to your existing backend.

---

## 🏗️ Architecture Overview

Your project has two parts:

1. **Backend** - FastAPI application (Python) in `flight-test-interactive-analysis-suite` repo
2. **Frontend** - React application (TypeScript) created by Manus in `ftias-frontend`

---

## 📋 Prerequisites

- **Node.js** 18+ and pnpm installed
- **Python** 3.11+ installed
- **PostgreSQL** database running locally
- **Git** for cloning repositories

---

## 🔧 Setup Instructions

### **Step 1: Merge Frontend into Your Existing Repository**

```bash
# Navigate to your existing backend repository
cd /path/to/flight-test-interactive-analysis-suite

# Download the frontend files from Manus
# (You can download the checkpoint as a zip file from the Manus UI)

# Copy the frontend files into your repo's frontend directory
# The frontend directory should contain:
# - client/
# - server/
# - drizzle/
# - package.json
# - etc.

# Commit the changes
git add frontend/
git commit -m "feat: add React frontend for flight test management"
git push origin main
```

---

### **Step 2: Set Up Environment Variables**

The frontend uses **tRPC** to communicate with the backend, but your existing backend uses **FastAPI REST API**. You need to create a **proxy layer** or **update the backend** to support tRPC.

#### **Option A: Create API Proxy (Easier)**

Create a `.env` file in the frontend directory:

```env
# Frontend .env file
VITE_API_URL=http://localhost:8000
DATABASE_URL=postgresql://ftias_user:ftias_password@localhost:5432/ftias_db
```

#### **Option B: Integrate Backend with tRPC (Better long-term)**

This would require refactoring your FastAPI backend to support tRPC, which is more complex but provides better type safety.

---

### **Step 3: Run the Backend**

```bash
# Navigate to backend directory
cd /path/to/flight-test-interactive-analysis-suite/backend

# Activate virtual environment (if using one)
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the backend server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The backend should now be running at `http://localhost:8000`

---

### **Step 4: Run the Frontend**

```bash
# Navigate to frontend directory
cd /path/to/flight-test-interactive-analysis-suite/frontend

# Install dependencies
pnpm install

# Run database migrations
pnpm db:push

# Start the development server
pnpm dev
```

The frontend should now be running at `http://localhost:3000`

---

## 🔌 Connecting Frontend to Backend

The frontend I created uses **tRPC** for API communication, but your existing backend uses **FastAPI REST endpoints**. You have two options:

### **Option 1: Update Frontend to Use REST API** (Recommended for now)

Modify the frontend's tRPC calls to use your existing REST API:

1. Create an API client in `client/src/lib/api.ts`:

```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add auth token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
```

Replace tRPC calls with REST API calls in your components.

### **Option 2: Add tRPC Support to Backend** (Better long-term)

This would require significant backend changes. I can help you with this if you'd like.

---

## 🐳 Using Docker (Alternative)

If you prefer to use Docker:

```bash
# From the project root
docker-compose up

# This will start:
# - PostgreSQL database
# - FastAPI backend
# - React frontend (if you add it to docker-compose.yml)
```

---

## ✅ Verification

Once both are running:

1. Open `http://localhost:3000` in your browser
2. You should see the Flight Test dashboard
3. Try creating a new flight test
4. Check that data is being saved to your PostgreSQL database

---

## 🔍 Troubleshooting

### **CORS Errors**

If you see CORS errors in the browser console, add CORS middleware to your FastAPI backend:

```python
# In backend/app/main.py
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### **Database Connection Issues**

Make sure PostgreSQL is running and the connection string in `.env` is correct.

### **Port Already in Use**

If port 3000 or 8000 is already in use, change the port in the respective configuration files.

---

## 📚 Next Steps

1. **Integrate Authentication** - Connect the frontend's auth system with your backend's JWT authentication
2. **Test File Uploads** - Verify CSV and Excel upload functionality works with your backend endpoints
3. **Deploy** - Once everything works locally, deploy both frontend and backend to production

---

## 🆘 Need Help?

If you encounter any issues, feel free to ask! I can help you:

- Merge the frontend into your existing repository
- Update the frontend to use your REST API
- Add tRPC support to your backend
- Set up Docker for local development
