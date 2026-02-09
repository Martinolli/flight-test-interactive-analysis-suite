# FTIAS Docker Environment

This directory contains Docker configuration files for the FTIAS development environment.

## Files

- `backend.Dockerfile` - Backend (FastAPI) container configuration
- `frontend.Dockerfile` - Frontend (React + Vite) container configuration

## Quick Start

### 1. Setup Environment Variables

Copy the example environment file and customize it:

```bash
cp .env.example .env
```

Edit `.env` and update the values as needed (especially passwords and secret keys).

### 2. Start All Services

```bash
docker-compose up
```

Or run in detached mode:

```bash
docker-compose up -d
```

### 3. Access Services

- **Frontend:** [http://localhost:5173](http://localhost:5173)
- **Backend API:** [http://localhost:8000](http://localhost:8000)
- **API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **pgAdmin (optional):** [http://localhost:5050](http://localhost:5050)

### 4. Stop Services

```bash
docker-compose down
```

To also remove volumes (database data):

```bash
docker-compose down -v
```

## Service Details

### PostgreSQL Database

- **Image:** postgres:15-alpine
- **Port:** 5432 (configurable via `POSTGRES_PORT`)
- **Default Database:** ftias_db
- **Default User:** ftias_user
- **Data Persistence:** Docker volume `postgres_data`

### Backend (FastAPI)

- **Base Image:** python:3.12-slim
- **Port:** 8000 (configurable via `BACKEND_PORT`)
- **Hot Reload:** Enabled (changes to code automatically restart the server)
- **Volume Mount:** `./backend` → `/app`

### Frontend (React + Vite)

- **Base Image:** node:20-alpine
- **Port:** 5173 (configurable via `FRONTEND_PORT`)
- **Hot Reload:** Enabled (changes to code automatically refresh the browser)
- **Volume Mount:** `./frontend` → `/app`

### pgAdmin (Optional)

To start pgAdmin for database management:

```bash
docker-compose --profile tools up pgadmin
```

Default credentials:

- **Email:** <admin@ftias.local>
- **Password:** admin

## Common Commands

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres
```

### Restart a Service

```bash
docker-compose restart backend
```

### Rebuild Containers

After changing Dockerfile or requirements:

```bash
docker-compose build
docker-compose up
```

Or force rebuild:

```bash
docker-compose up --build
```

### Execute Commands in Containers

```bash
# Backend shell
docker-compose exec backend bash

# Frontend shell
docker-compose exec frontend sh

# PostgreSQL shell
docker-compose exec postgres psql -U ftias_user -d ftias_db
```

### Database Operations

```bash
# Create database backup
docker-compose exec postgres pg_dump -U ftias_user ftias_db > backup.sql

# Restore database backup
docker-compose exec -T postgres psql -U ftias_user -d ftias_db < backup.sql

# Access PostgreSQL CLI
docker-compose exec postgres psql -U ftias_user -d ftias_db
```

## Troubleshooting

### Port Already in Use

If you get a "port already in use" error, either:

1. Stop the service using that port
2. Change the port in `.env` file

### Permission Issues (Linux/Mac)

If you encounter permission issues with volumes:

```bash
sudo chown -R $USER:$USER ./backend ./frontend ./database
```

### Container Won't Start

Check logs for errors:

```bash
docker-compose logs backend
```

### Database Connection Issues

1. Ensure PostgreSQL is healthy:

   ```bash
   docker-compose ps
   ```

2. Check database logs:

   ```bash
   docker-compose logs postgres
   ```

3. Verify connection from backend:

   ```bash
   docker-compose exec backend python -c "from sqlalchemy import create_engine; engine = create_engine('postgresql://ftias_user:ftias_password@postgres:5432/ftias_db'); print(engine.connect())"
   ```

### Clean Start

To completely reset the environment:

```bash
docker-compose down -v
docker-compose build --no-cache
docker-compose up
```

## Development Workflow

1. **Start the environment:**

   ```bash
   docker-compose up
   ```

2. **Make code changes** in `./backend` or `./frontend`

3. **Changes are automatically reflected** (hot reload enabled)

4. **Run tests:**

   ```bash
   # Backend tests
   docker-compose exec backend pytest
   
   # Frontend tests
   docker-compose exec frontend pnpm test
   ```

5. **Stop when done:**

   ```bash
   docker-compose down
   ```

## Production Considerations

This Docker setup is optimized for **development**. For production:

- Use multi-stage builds to reduce image size
- Remove hot reload and development dependencies
- Use proper secrets management (not .env files)
- Configure proper logging and monitoring
- Use production-grade web servers (e.g., Nginx)
- Implement proper health checks and restart policies
- Use Docker Swarm or Kubernetes for orchestration

## Network Architecture

All services are connected via the `ftias-network` bridge network:

```bash
┌─────────────────────────────────────────┐
│         ftias-network (bridge)          │
│                                         │
│  ┌──────────┐  ┌──────────┐  ┌────────┐│
│  │ Frontend │  │ Backend  │  │Postgres││
│  │  :5173   │→ │  :8000   │→ │ :5432  ││
│  └──────────┘  └──────────┘  └────────┘│
│                                         │
│       ┌──────────┐                      │
│       │ pgAdmin  │                      │
│       │  :5050   │                      │
│       └──────────┘                      │
└─────────────────────────────────────────┘
```

## Environment Variables Reference

See `.env.example` for all available environment variables and their descriptions.

## Support

For issues or questions:

1. Check the troubleshooting section above
2. Review Docker logs: `docker-compose logs`
3. Consult the main project documentation
4. Open an issue on GitHub
