# FTIAS Docker Integration Verification Guide

**Project:** Flight Test Interactive Analysis Suite (FTIAS)
**Date:** February 10, 2026
**Author:** Manus AI

---

## Introduction

This guide provides a comprehensive set of command-line instructions to verify that your Docker integration for the FTIAS project is working correctly. Follow these steps sequentially to build, run, and test the application in a containerized environment.

**Prerequisites:**

- Docker Desktop is installed and running.
- You are in the root directory of the `flight-test-interactive-analysis-suite` project in your terminal.

---

## Part 1: Basic Docker & Docker Compose Verification

First, let's ensure that Docker and Docker Compose are installed and accessible from your terminal.

### 1.1 Check Docker Version

```bash
docker --version
```

**Expected Output:**

```bash
Docker version 25.0.3, build 4debf41
```

**(Your version may vary, but you should see a version number.)*

### 1.2 Check Docker Compose Version

```bash
docker compose version
```

**Expected Output:**

```bash
Docker Compose version v2.24.6
```

**(Your version may vary.)*

---

## Part 2: Docker Compose File Validation

Next, let's validate the syntax of your `docker-compose.yml` files. This step catches any formatting errors before you attempt to build or run the services.

### 2.1 Validate Main `docker-compose.yml`

```bash
docker compose -f docker-compose.yml config
```

**Expected Output:**
The command will print the fully resolved YAML configuration to the terminal if it's valid. If there are errors, it will report them.

### 2.2 Validate Backend-Only `docker-compose.yml`

```bash
docker compose -f docker-compose.backend-only.yml config
```

**Expected Output:**
Similar to the previous command, this will print the resolved configuration for the backend-only setup.

---

## Part 3: Building the Docker Images

Now, let's build the Docker images for the services defined in your `docker-compose.yml` file. This command reads the `Dockerfile` for each service and creates the images.

### 3.1 Build All Services

```bash
docker compose build
```

**Expected Output:**
You will see a series of build steps for each service (`db`, `backend`, `frontend`). This may take a few minutes the first time you run it.

### 3.2 (Optional) Rebuild a Specific Service

If you only made changes to the backend, you can rebuild just that image to save time.

```bash
docker compose build backend
```

---

## Part 4: Running the Application

Once the images are built, you can start the application. We'll use the `-d` flag to run the containers in detached mode (in the background).

```bash
docker compose up -d
```

**Expected Output:**

```bash
[+] Running 3/3
 ✔ Container ftias-db-1       Started                                                                    0.8s
 ✔ Container ftias-backend-1  Started                                                                    1.2s
 ✔ Container ftias-frontend-1 Started                                                                    1.5s
```

---

## Part 5: Verifying Running Services

After starting the containers, let's check their status to ensure they are running correctly.

### 5.1 Check Container Status with Docker Compose

```bash
docker compose ps
```

**Expected Output:**
This will show a table with the status of your containers. All services should have a `State` of `Up` or `running`.

| NAME | COMMAND | SERVICE | STATUS | PORTS |
| --- | --- | --- | --- | --- |
| ftias-backend-1 | "uvicorn app.main:app…" | backend | running | 0.0.0.0:8000->8000/tcp |
| ftias-db-1 | "docker-entrypoint.sh…" | db | running | 5432/tcp |
| ftias-frontend-1 | "npm run dev" | frontend | running | 0.0.0.0:5173->5173/tcp |

### 5.2 Check Container Status with Docker

For a more detailed view, you can use the standard `docker ps` command.

```bash
docker ps
```

---

## Part 6: Checking Logs

If a container is not running as expected, checking its logs is the best way to diagnose the problem.

### 6.1 View Backend Logs

Use the `-f` flag to follow the logs in real-time.

```bash
docker compose logs -f backend
```

**Expected Output:**
You should see the Uvicorn server startup messages, including:

```bash
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [1] using StatReload
INFO:     Started server process [8]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### 6.2 View Database Logs

```bash
docker compose logs db
```

**Expected Output:**

You should see PostgreSQL initialization messages, ending with something like:

```bash
db-1  | LOG:  database system is ready to accept connections
```

---

## Part 7: Testing the Application

With the services running, let's test the backend API to ensure it's operational and connected to the database.

```bash
curl http://localhost:8000/api/health
```

**Expected Output:**
A successful response indicates that the backend is running and can connect to the database.

```json
{
  "status": "ok",
  "database_status": "connected"
}
```

---

## Part 8: Stopping and Cleaning Up

Once you're finished, you can stop and remove the containers.

### 8.1 Stop and Remove Containers

```bash
docker compose down
```

**Expected Output:**

```bash
[+] Running 3/3
 ✔ Container ftias-frontend-1 Removed                                                                   0.5s
 ✔ Container ftias-backend-1  Removed                                                                   0.8s
 ✔ Container ftias-db-1       Removed                                                                   1.1s
```

### 8.2 Stop and Remove Containers and Volumes

To remove the database data as well, use the `-v` flag. **Warning:** This will delete all data in your Docker database volume.

```bash
docker compose down -v
```

---

## Troubleshooting

- **Port Conflicts:** If you get an error about a port being already allocated, make sure no other application is using port 8000, 5173, or 5432.
- **Container Fails to Start:** If a container exits immediately, check its logs (`docker compose logs <service_name>`) for error messages.
- **Build Failures:** Build failures are often due to missing dependencies or syntax errors in the `Dockerfile`. Review the error messages from the build process carefully.

This guide should help you thoroughly verify your Docker setup. If you encounter any issues, please share the command you ran and the full error message.
