# FTIAS Docker Environment

This directory contains Docker configuration files for the Flight Test Interactive Analysis Suite (FTIAS) development environment.

## Overview

The FTIAS project uses Docker and Docker Compose to provide a consistent, reproducible development environment across all platforms (Windows, macOS, Linux). This approach ensures that all developers work with the same versions of dependencies and services.

## Directory Contents

```
docker/
├── README.md              # This file - Docker documentation
├── backend.Dockerfile     # Backend (FastAPI) container configuration
├── frontend.Dockerfile    # Frontend (React + Vite) container configuration
└── .gitkeep              # Git tracking placeholder
```

## Architecture

The FTIAS Docker environment consists of four services:

1. **PostgreSQL Database** - Stores flight test data, parameters, and user information
2. **Backend API (FastAPI)** - Python-based REST API server
3. **Frontend (React + Vite)** - Web-based user interface
4. **pgAdmin (Optional)** - Database management tool

All services are connected via a Docker bridge network (`ftias-network`) and orchestrated using Docker Compose.

---

## Prerequisites

### Required Software

- **Docker Desktop** (Windows/Mac) or **Docker Engine** (Linux)
  - Windows: [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
  - Mac: [Download Docker Desktop](https://www.docker.com/products/docker-desktop/)
  - Linux: [Install Docker Engine](https://docs.docker.com/engine/install/)

- **Docker Compose** (included with Docker Desktop)
  - Minimum version: 2.0+
  - Check version: `docker-compose --version`

### Verify Installation

```powershell
# Check Docker is installed and running
docker --version
docker info

# Check Docker Compose is installed
docker-compose --version
```

---

## Quick Start Guide

### Step 1: Clone Repository

```powershell
git clone https://github.com/Martinolli/flight-test-interactive-analysis-suite.git
cd flight-test-interactive-analysis-suite
```

### Step 2: Create Environment File

```powershell
# Copy the example environment file
cp .env.example .env

# Edit .env and update the following (minimum):
# - SECRET_KEY (generate a random 32+ character string)
# - JWT_SECRET_KEY (generate a random 32+ character string)
# - POSTGRES_PASSWORD (choose a secure password)
```

**Important:** Never commit the `.env` file to Git. It contains sensitive credentials.

### Step 3: Start Services

```powershell
# Start all services (first run will download images)
docker-compose up

# Or start in detached mode (runs in background)
docker-compose up -d
```

**First Run:** Docker will download images (~2GB) which may take 5-10 minutes depending on your internet connection.

### Step 4: Verify Services

```powershell
# Check all services are running
docker-compose ps

# Expected output:
# NAME              STATUS    PORTS
# ftias-postgres    Up        0.0.0.0:5432->5432/tcp
# ftias-backend     Up        0.0.0.0:8000->8000/tcp
# ftias-frontend    Up        0.0.0.0:5173->5173/tcp
```

### Step 5: Access Services

Open your web browser and navigate to:

- **Frontend Application:** http://localhost:5173
- **Backend API:** http://localhost:8000
- **API Documentation (Swagger):** http://localhost:8000/docs
- **API Documentation (ReDoc):** http://localhost:8000/redoc

---

## Service Details

### PostgreSQL Database

**Container Name:** `ftias-postgres`

**Configuration:**
- **Image:** `postgres:15-alpine`
- **Port:** `5432` (configurable via `POSTGRES_PORT` in `.env`)
- **Database:** `ftias_db` (configurable via `POSTGRES_DB`)
- **User:** `ftias_user` (configurable via `POSTGRES_USER`)
- **Password:** Set in `.env` file (`POSTGRES_PASSWORD`)

**Data Persistence:**
- Data is stored in Docker volume `postgres_data`
- Survives container restarts and rebuilds
- Initialization scripts in `database/init/` run on first startup

**Health Check:**
- Checks database is ready to accept connections
- Other services wait for database to be healthy before starting

### Backend API (FastAPI)

**Container Name:** `ftias-backend`

**Configuration:**
- **Base Image:** `python:3.12-slim`
- **Port:** `8000` (configurable via `BACKEND_PORT`)
- **Working Directory:** `/app`
- **Source Code:** Mounted from `./backend`

**Features:**
- **Hot Reload:** Code changes automatically restart the server
- **Auto-reload:** Enabled via `--reload` flag in uvicorn
- **Dependencies:** Installed from `backend/requirements.txt`

**Environment Variables:**
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - Application secret key
- `DEBUG` - Debug mode (true for development)
- `CORS_ORIGINS` - Allowed CORS origins

### Frontend (React + Vite)

**Container Name:** `ftias-frontend`

**Configuration:**
- **Base Image:** `node:20-alpine`
- **Port:** `5173` (configurable via `FRONTEND_PORT`)
- **Working Directory:** `/app`
- **Source Code:** Mounted from `./frontend`

**Features:**
- **Hot Module Replacement (HMR):** Instant updates without page refresh
- **Fast Refresh:** Preserves component state during updates
- **Package Manager:** pnpm (faster than npm)

**Environment Variables:**
- `VITE_API_URL` - Backend API URL (default: http://localhost:8000)
- `NODE_ENV` - Node environment (development/production)

### pgAdmin (Optional)

**Container Name:** `ftias-pgadmin`

**Configuration:**
- **Image:** `dpage/pgadmin4:latest`
- **Port:** `5050` (configurable via `PGADMIN_PORT`)
- **Profile:** `tools` (not started by default)

**Starting pgAdmin:**
```powershell
docker-compose --profile tools up pgadmin
```

**Access:**
- **URL:** http://localhost:5050
- **Email:** `admin@ftias.local` (configurable via `PGADMIN_EMAIL`)
- **Password:** `admin` (configurable via `PGADMIN_PASSWORD`)

**Connecting to Database:**
1. Open pgAdmin at http://localhost:5050
2. Right-click "Servers" → "Register" → "Server"
3. **General Tab:** Name: `FTIAS Database`
4. **Connection Tab:**
   - Host: `postgres` (container name)
   - Port: `5432`
   - Database: `ftias_db`
   - Username: `ftias_user`
   - Password: (from your `.env` file)

---

## Common Operations

### Starting Services

```powershell
# Start all services with logs
docker-compose up

# Start in detached mode (background)
docker-compose up -d

# Start specific service only
docker-compose up postgres
docker-compose up backend
docker-compose up frontend

# Start with pgAdmin
docker-compose --profile tools up
```

### Stopping Services

```powershell
# Stop all services (keeps containers)
docker-compose stop

# Stop and remove containers
docker-compose down

# Stop and remove containers + volumes (deletes database data)
docker-compose down -v

# Stop specific service
docker-compose stop backend
```

### Viewing Logs

```powershell
# View logs from all services
docker-compose logs

# Follow logs in real-time
docker-compose logs -f

# View logs from specific service
docker-compose logs backend
docker-compose logs -f frontend

# View last 100 lines
docker-compose logs --tail=100

# View logs with timestamps
docker-compose logs -f -t
```

### Restarting Services

```powershell
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart backend
docker-compose restart frontend

# Restart with rebuild
docker-compose up --build
```

### Rebuilding Images

```powershell
# Rebuild all images
docker-compose build

# Rebuild specific service
docker-compose build backend
docker-compose build frontend

# Rebuild without cache (clean build)
docker-compose build --no-cache

# Rebuild and start
docker-compose up --build
```

---

## Development Workflow

### Typical Development Session

```powershell
# 1. Start services
docker-compose up -d

# 2. View logs (optional)
docker-compose logs -f

# 3. Make code changes in ./backend or ./frontend
# Changes are automatically detected and applied

# 4. When done, stop services
docker-compose down
```

### Working with Backend

```powershell
# Access backend container shell
docker-compose exec backend bash

# Inside container:
# - Run tests: pytest
# - Check dependencies: pip list
# - Run migrations: alembic upgrade head
# - Format code: black .
# - Lint code: flake8 .

# Run command without entering shell
docker-compose exec backend pytest
docker-compose exec backend black .
```

### Working with Frontend

```powershell
# Access frontend container shell
docker-compose exec frontend sh

# Inside container:
# - Install package: pnpm add <package>
# - Run tests: pnpm test
# - Build: pnpm build
# - Lint: pnpm lint

# Run command without entering shell
docker-compose exec frontend pnpm test
docker-compose exec frontend pnpm lint
```

### Working with Database

```powershell
# Access PostgreSQL CLI
docker-compose exec postgres psql -U ftias_user -d ftias_db

# Inside psql:
# - List tables: \dt
# - Describe table: \d table_name
# - Run query: SELECT * FROM users;
# - Exit: \q

# Run SQL query directly
docker-compose exec postgres psql -U ftias_user -d ftias_db -c "SELECT version();"

# Create database backup
docker-compose exec postgres pg_dump -U ftias_user ftias_db > backup.sql

# Restore database backup
docker-compose exec -T postgres psql -U ftias_user -d ftias_db < backup.sql
```

---

## Troubleshooting

### Services Won't Start

**Check Docker is running:**
```powershell
docker info
```

**Check for port conflicts:**
```powershell
# Windows
netstat -ano | findstr :5432
netstat -ano | findstr :8000
netstat -ano | findstr :5173

# Change ports in .env if needed
```

**View error logs:**
```powershell
docker-compose logs
```

### Database Connection Errors

**Ensure database is healthy:**
```powershell
docker-compose ps
# postgres should show "healthy" status
```

**Check database logs:**
```powershell
docker-compose logs postgres
```

**Verify connection string:**
```powershell
docker-compose exec backend env | grep DATABASE_URL
```

### Backend Won't Start

**Check Dockerfile exists:**
```powershell
ls docker/backend.Dockerfile
```

**Check requirements.txt exists:**
```powershell
ls backend/requirements.txt
```

**Rebuild backend:**
```powershell
docker-compose build backend
docker-compose up backend
```

### Frontend Won't Start

**Check Dockerfile exists:**
```powershell
ls docker/frontend.Dockerfile
```

**Check package.json exists:**
```powershell
ls frontend/package.json
```

**Rebuild frontend:**
```powershell
docker-compose build frontend
docker-compose up frontend
```

### Clean Slate (Nuclear Option)

If all else fails, completely reset Docker environment:

```powershell
# Stop and remove everything
docker-compose down -v

# Remove all FTIAS images
docker images | grep ftias | awk '{print $3}' | xargs docker rmi

# Remove all dangling images
docker image prune -a

# Start fresh
docker-compose up --build
```

---

## Performance Optimization

### Windows/Mac Performance

Docker Desktop on Windows/Mac can be slower than native Linux. To improve performance:

1. **Allocate More Resources:**
   - Open Docker Desktop → Settings → Resources
   - Increase CPUs to 4+ and Memory to 8GB+

2. **Enable WSL 2 (Windows):**
   - Docker Desktop → Settings → General
   - Check "Use the WSL 2 based engine"

3. **Use Named Volumes for node_modules:**
   - Already configured in `docker-compose.yml`
   - Prevents slow file system operations

### Build Cache

Docker caches build layers to speed up rebuilds:

```powershell
# Use cache (fast)
docker-compose build

# Ignore cache (slow but clean)
docker-compose build --no-cache
```

---

## Production Deployment

**Warning:** This Docker setup is optimized for **development**, not production.

For production deployment, you need:

1. **Multi-stage Builds** - Reduce image size
2. **Production Web Server** - Nginx for frontend, Gunicorn for backend
3. **Environment Variables** - Proper secrets management
4. **Health Checks** - Comprehensive monitoring
5. **Logging** - Centralized log aggregation
6. **Security** - Non-root users, security scanning
7. **Orchestration** - Kubernetes or Docker Swarm

Refer to the deployment documentation when ready for production.

---

## Network Architecture

```
┌─────────────────────────────────────────────────────┐
│           ftias-network (bridge)                    │
│                                                     │
│  ┌──────────────┐      ┌──────────────┐           │
│  │   Frontend   │──────│   Backend    │           │
│  │ React + Vite │      │   FastAPI    │           │
│  │   :5173      │      │    :8000     │           │
│  └──────────────┘      └──────┬───────┘           │
│                                │                    │
│                        ┌───────▼───────┐           │
│                        │   PostgreSQL  │           │
│                        │     :5432     │           │
│                        └───────────────┘           │
│                                                     │
│                        ┌───────────────┐           │
│                        │    pgAdmin    │           │
│                        │     :5050     │           │
│                        └───────────────┘           │
└─────────────────────────────────────────────────────┘
                           │
                           │ Port Mapping
                           ▼
                    Host Machine
              (localhost:5173, :8000, :5432)
```

---

## Environment Variables Reference

See `.env.example` for all available environment variables and their descriptions.

**Critical Variables:**
- `SECRET_KEY` - Application secret (must be changed)
- `JWT_SECRET_KEY` - JWT signing key (must be changed)
- `POSTGRES_PASSWORD` - Database password (must be changed)

**Optional Variables:**
- `POSTGRES_PORT` - Database port (default: 5432)
- `BACKEND_PORT` - API port (default: 8000)
- `FRONTEND_PORT` - Frontend port (default: 5173)
- `DEBUG` - Debug mode (default: true)

---

## Additional Resources

- **Docker Documentation:** https://docs.docker.com/
- **Docker Compose Documentation:** https://docs.docker.com/compose/
- **FastAPI Documentation:** https://fastapi.tiangolo.com/
- **Vite Documentation:** https://vitejs.dev/
- **PostgreSQL Documentation:** https://www.postgresql.org/docs/

---

## Support

For Docker-related issues:
1. Check this README
2. Review `Docker_Troubleshooting_Guide.md` in project root
3. Check Docker logs: `docker-compose logs`
4. Open an issue on GitHub with the `docker` label

---

**Last Updated:** February 5, 2026  
**Docker Compose Version:** 5.0.2  
**Maintained by:** FTIAS Development Team
