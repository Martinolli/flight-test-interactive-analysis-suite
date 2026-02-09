# Backend Testing Guide - FTIAS

**Date:** February 6, 2026  
**Phase:** Hybrid Approach - Phase 2  
**Status:** Ready to Test Docker Environment

---

## What We've Built

A minimal but functional FastAPI backend with:

✅ **9 Python files** created  
✅ **8 API endpoints** implemented  
✅ **Database models** (User)  
✅ **CRUD operations** (Create, Read, Update, Delete)  
✅ **Health checks** with database status  
✅ **Password hashing** (bcrypt)  
✅ **API documentation** (Swagger/ReDoc)

---

## Testing Steps

### Step 1: Commit Backend Code

First, commit the new backend code to your repository:

```powershell
# In your project root
git add backend/app/
git commit -m "feat(backend): add minimal FastAPI backend with user CRUD and health checks"
git push origin main
```

### Step 2: Verify Docker Desktop is Running

```powershell
# Check Docker status
docker info

# Should show Docker server information
# If error, start Docker Desktop and wait for it to be ready
```

### Step 3: Start Docker Services

```powershell
# Navigate to project root
cd "C:\Users\Aspire5 15 i7 4G2050\flight-test-interactive-analysis-suite"

# Start all services (first time will build images)
docker-compose up

# Or start in detached mode (background)
docker-compose up -d
```

**Expected Output:**
```
[+] Running 3/3
 ✔ Container ftias-postgres  Started
 ✔ Container ftias-backend   Started
 ✔ Container ftias-frontend  Started (will fail - no frontend yet)
```

**Note:** Frontend will fail (no React app yet), but that's expected!

### Step 4: Check Service Status

```powershell
# View running containers
docker-compose ps

# Expected:
# ftias-postgres   Up (healthy)
# ftias-backend    Up
# ftias-frontend   Exit (expected failure)
```

### Step 5: View Backend Logs

```powershell
# View backend logs
docker-compose logs backend

# Or follow logs in real-time
docker-compose logs -f backend

# Look for:
# 🚀 FTIAS Backend starting...
# 📊 Database: postgresql://...
# Uvicorn running on http://0.0.0.0:8000
```

### Step 6: Test API Endpoints

Open your web browser and test these URLs:

#### 1. Root Endpoint
```
http://localhost:8000/
```

**Expected Response:**
```json
{
  "message": "Welcome to FTIAS API",
  "version": "0.1.0",
  "status": "running",
  "docs": "/docs"
}
```

#### 2. Health Check
```
http://localhost:8000/api/health
```

**Expected Response:**
```json
{
  "status": "healthy",
  "database": "connected",
  "timestamp": "2026-02-06T..."
}
```

#### 3. Ping Endpoint
```
http://localhost:8000/api/ping
```

**Expected Response:**
```json
{
  "message": "pong",
  "timestamp": "2026-02-06T..."
}
```

#### 4. API Documentation
```
http://localhost:8000/docs
```

**Expected:** Interactive Swagger UI with all endpoints

#### 5. Alternative Documentation
```
http://localhost:8000/redoc
```

**Expected:** ReDoc documentation interface

---

## Testing CRUD Operations

### Using Swagger UI (Easiest)

1. Open http://localhost:8000/docs
2. Click on any endpoint to expand it
3. Click "Try it out"
4. Fill in the request body
5. Click "Execute"

### Using curl (Command Line)

#### Create a User

```powershell
curl -X POST "http://localhost:8000/api/users/" `
  -H "Content-Type: application/json" `
  -d '{
    "email": "test@example.com",
    "username": "testuser",
    "full_name": "Test User",
    "password": "securepassword123"
  }'
```

**Expected Response:**
```json
{
  "id": 1,
  "email": "test@example.com",
  "username": "testuser",
  "full_name": "Test User",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2026-02-06T...",
  "updated_at": null
}
```

#### Get All Users

```powershell
curl http://localhost:8000/api/users/
```

#### Get User by ID

```powershell
curl http://localhost:8000/api/users/1
```

#### Update User

```powershell
curl -X PUT "http://localhost:8000/api/users/1" `
  -H "Content-Type: application/json" `
  -d '{
    "full_name": "Updated Name"
  }'
```

#### Delete User

```powershell
curl -X DELETE http://localhost:8000/api/users/1
```

---

## Troubleshooting

### Issue: Backend Container Won't Start

**Check logs:**
```powershell
docker-compose logs backend
```

**Common issues:**
- Missing dependencies → Rebuild: `docker-compose build backend`
- Database not ready → Wait 30 seconds and try again
- Port 8000 in use → Change `BACKEND_PORT` in `.env`

### Issue: Database Connection Error

**Check database status:**
```powershell
docker-compose ps postgres
# Should show "Up (healthy)"
```

**Check database logs:**
```powershell
docker-compose logs postgres
```

**Verify connection:**
```powershell
docker-compose exec postgres psql -U ftias_user -d ftias_db -c "SELECT version();"
```

### Issue: Import Errors

**Rebuild backend:**
```powershell
docker-compose build --no-cache backend
docker-compose up backend
```

### Issue: Port Already in Use

**Change ports in `.env`:**
```
BACKEND_PORT=8001
POSTGRES_PORT=5433
```

Then restart:
```powershell
docker-compose down
docker-compose up
```

---

## Verification Checklist

Use this checklist to verify everything works:

- [ ] Docker Desktop is running
- [ ] `docker-compose up` starts without errors
- [ ] PostgreSQL container is healthy
- [ ] Backend container is running
- [ ] http://localhost:8000/ returns welcome message
- [ ] http://localhost:8000/api/health shows "healthy" status
- [ ] http://localhost:8000/docs shows Swagger UI
- [ ] Can create a user via Swagger UI
- [ ] Can retrieve users via GET /api/users/
- [ ] Can update a user
- [ ] Can delete a user
- [ ] Backend logs show no errors

---

## Expected Results

### ✅ Success Indicators

1. **Backend starts successfully**
   - No Python import errors
   - Database connection established
   - Uvicorn running on port 8000

2. **Health check passes**
   - Status: "healthy"
   - Database: "connected"

3. **CRUD operations work**
   - Can create users
   - Can read users
   - Can update users
   - Can delete users

4. **API documentation accessible**
   - Swagger UI loads
   - All endpoints visible
   - Can test endpoints interactively

### ⚠️ Expected Failures

1. **Frontend container fails**
   - This is normal - no React app yet
   - Will be fixed in Sprint 2

---

## Next Steps After Testing

Once you've verified the backend works:

1. **Commit and push** any changes
2. **Proceed to Phase 3** - Add CI/CD pipeline
3. **Celebrate** - You have a working backend! 🎉

---

## Quick Commands Reference

```powershell
# Start services
docker-compose up

# Start in background
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f backend

# Rebuild backend
docker-compose build backend

# Restart backend
docker-compose restart backend

# Access backend shell
docker-compose exec backend bash

# Access database
docker-compose exec postgres psql -U ftias_user -d ftias_db

# Check service status
docker-compose ps
```

---

## Testing Workflow

Recommended testing workflow:

1. **Start services:** `docker-compose up -d`
2. **Check logs:** `docker-compose logs -f backend`
3. **Test health:** http://localhost:8000/api/health
4. **Open Swagger:** http://localhost:8000/docs
5. **Create user:** Use Swagger UI
6. **Test CRUD:** Try all operations
7. **Check database:** Verify data persists
8. **Stop services:** `docker-compose down`

---

## Ready to Test?

You're all set! Follow the steps above to test your Docker environment.

**Estimated Time:** 15-30 minutes

Let me know if you encounter any issues!
