# Docker Troubleshooting Guide for FTIAS

**Date:** February 5, 2026
**Issue:** Docker Desktop connection error and docker-compose warnings

---

## Issue 1: Docker Desktop Not Running

### Error Message

```BASH
unable to get image 'flight-test-interactive-analysis-suite-frontend':
error during connect: Get "http://%2F%2F.%2Fpipe%2FdockerDesktopLinuxEngine/v1.51/images/...":
open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.
```

### Root Cause

Docker Desktop is not running or not properly started on Windows.

### Solution

#### Step 1: Start Docker Desktop

1. **Open Docker Desktop** from Windows Start menu
2. **Wait for complete startup** (usually 30-60 seconds)
3. **Check system tray** for Docker icon - should show "Docker Desktop is running"

#### Step 2: Verify Docker is Running

```powershell
# Check Docker daemon status
docker info

# Expected output: Docker server information
# If error: Docker Desktop is not running
```

```powershell
# Check Docker version
docker --version
docker-compose --version

# Expected output:
# Docker version 28.3.2, build 578ccf6
# Docker Compose version v2.39.1-desktop.1
```

#### Step 3: Test Docker Connection

```powershell
# Run a simple test container
docker run hello-world

# Expected output:
# "Hello from Docker!"
# If this works, Docker is properly connected
```

### Common Docker Desktop Issues

#### Issue A: Docker Desktop Won't Start

**Symptoms:**

- Docker Desktop stuck on "Starting..."
- Error: "Docker Desktop failed to start"

**Solutions:**

1. **Restart Docker Desktop:**
   - Right-click Docker icon in system tray
   - Select "Quit Docker Desktop"
   - Wait 10 seconds
   - Start Docker Desktop again

2. **Restart WSL 2 (if using WSL 2 backend):**

   ```powershell
   # In PowerShell (as Administrator)
   wsl --shutdown
   # Wait 10 seconds, then start Docker Desktop
   ```

3. **Check Windows Services:**
   - Press `Win + R`, type `services.msc`
   - Find "Docker Desktop Service"
   - Ensure it's running, if not, right-click → Start

4. **Reinstall Docker Desktop:**
   - Uninstall Docker Desktop
   - Restart computer
   - Download latest version from docker.com
   - Install and restart

#### Issue B: Docker Desktop Requires Update

**Symptoms:**

- Warning: "Docker Desktop is out of date"

**Solution:**

- Click "Update" in Docker Desktop
- Or download latest version from docker.com

#### Issue C: WSL 2 Integration Issues

**Symptoms:**

- Error: "WSL 2 installation is incomplete"

**Solution:**

1. **Enable WSL 2:**

   ```powershell
   # In PowerShell (as Administrator)
   wsl --install
   wsl --set-default-version 2
   ```

2. **Update WSL:**

   ```powershell
   wsl --update
   ```

3. **Configure Docker Desktop:**
   - Open Docker Desktop Settings
   - Go to "General"
   - Ensure "Use the WSL 2 based engine" is checked

---

## Issue 2: Obsolete `version` Attribute Warning

### Warning Message

```BASH
level=warning msg="...\docker-compose.yml: the attribute `version` is obsolete,
it will be ignored, please remove it to avoid potential confusion"
```

### Root Cause 1

Docker Compose V2 no longer requires the `version` attribute in `docker-compose.yml`.

### Solution 1

#### Step 1: Remove Version Line

**Before:**

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    ...
```

**After:**

```yaml
services:
  postgres:
    image: postgres:15-alpine
    ...
```

#### Step 2: Commit the Change

```powershell
git add docker-compose.yml
git commit -m "fix(docker): remove obsolete version attribute from docker-compose.yml"
git push origin main
```

**Status:** ✅ **FIXED** - I've already removed the version line from docker-compose.yml

---

## Complete Docker Startup Procedure

### Prerequisites Checklist

- [ ] Docker Desktop installed
- [ ] Docker Desktop running (green icon in system tray)
- [ ] `.env` file exists in project root
- [ ] Backend and Frontend folders exist (even if empty)

### Step-by-Step Startup

#### 1. Verify Docker is Running

```powershell
# Check Docker status
docker info

# If error, start Docker Desktop and wait
```

#### 2. Navigate to Project Directory

```powershell
cd "C:\Users\Aspire5 15 i7 4G2050\flight-test-interactive-analysis-suite"
```

#### 3. Verify .env File Exists

```powershell
# Check if .env exists
Test-Path .env

# If False, create it from template
cp .env.example .env
```

#### 4. Start Docker Services

```powershell
# Start all services (first time will download images)
docker-compose up

# Or start in detached mode (runs in background)
docker-compose up -d
```

#### 5. Wait for Services to Start

**Expected output:**

```BASH
[+] Running 3/3
 ✔ Container ftias-postgres  Started
 ✔ Container ftias-backend   Started
 ✔ Container ftias-frontend  Started
```

**Note:** First run will take 5-10 minutes to download images.

#### 6. Verify Services are Running

```powershell
# Check running containers
docker-compose ps

# Expected output:
# NAME              STATUS    PORTS
# ftias-postgres    Up        0.0.0.0:5432->5432/tcp
# ftias-backend     Up        0.0.0.0:8000->8000/tcp
# ftias-frontend    Up        0.0.0.0:5173->5173/tcp
```

#### 7. Access Services

- **Frontend:** <http://localhost:5173>
- **Backend API:** <http://localhost:8000>
- **API Documentation:** <http://localhost:8000/docs>
- **Database:** <localhost:5432> (use pgAdmin or psql)

---

## Current Status: Cannot Start Services Yet

### Why Services Won't Start

Currently, the backend and frontend folders are **empty** (only contain `.gitkeep`). Docker cannot build these services because:

1. **Backend:** No `app/` directory or `main.py` file
2. **Frontend:** No `package.json` or React application

### Expected Behavior

When you run `docker-compose up` now, you'll see:

```BASH
ERROR: Cannot locate specified Dockerfile: docker/backend.Dockerfile
```

or

```BASH
ERROR: failed to solve: failed to read dockerfile:
open /var/lib/docker/.../backend/app/main.py: no such file or directory
```

### What We Need to Do Next

#### Option 1: Build Backend and Frontend (Sprint 2-3)

- Create FastAPI backend structure
- Create React frontend structure
- Then Docker will work

#### Option 2: Test Docker with Minimal Setup

- Create minimal backend (simple FastAPI app)
- Create minimal frontend (simple React app)
- Verify Docker works
- Then build full applications

### Recommendation

**For now, let's complete Sprint 1 Task 1.5 (CI/CD Pipeline) first.**

Once we start Sprint 2 (Backend Development), we'll:

1. Create the FastAPI application structure
2. Create the React application structure
3. Then test Docker with real applications

---

## Quick Reference Commands

### Start Services

```powershell
docker-compose up          # Start with logs
docker-compose up -d       # Start detached (background)
```

### Stop Services

```powershell
docker-compose down        # Stop and remove containers
docker-compose stop        # Stop containers (keep them)
```

### View Logs

```powershell
docker-compose logs -f              # All services
docker-compose logs -f backend      # Backend only
docker-compose logs -f frontend     # Frontend only
docker-compose logs -f postgres     # Database only
```

### Restart Services

```powershell
docker-compose restart              # Restart all
docker-compose restart backend      # Restart backend only
```

### Rebuild Services

```powershell
docker-compose build               # Rebuild all images
docker-compose up --build          # Rebuild and start
```

### Clean Up

```powershell
docker-compose down -v             # Stop and remove volumes
docker system prune -a             # Remove all unused images
```

### Access Container Shell

```powershell
docker-compose exec backend bash       # Backend shell
docker-compose exec frontend sh        # Frontend shell
docker-compose exec postgres psql -U ftias_user -d ftias_db  # Database
```

---

## Summary

### Issues Fixed

- ✅ Removed obsolete `version` attribute from `docker-compose.yml`

### Issues Requiring Action

- ⚠️ **Start Docker Desktop** (user action required)
- ⚠️ **Create backend and frontend applications** (Sprint 2-3)

### Next Steps

1. Start Docker Desktop
2. Verify Docker is running with `docker info`
3. Complete Sprint 1 Task 1.5 (CI/CD Pipeline)
4. Proceed to Sprint 2 (Backend Development)
5. Then test Docker with real applications

---

## Support

If you continue to have Docker issues:

1. Check Docker Desktop logs: Settings → Troubleshoot → View logs
2. Restart Docker Desktop
3. Restart computer
4. Reinstall Docker Desktop
5. Check Docker documentation: [https://docs.docker.com/desktop/windows/](https://docs.docker.com/desktop/windows/)
