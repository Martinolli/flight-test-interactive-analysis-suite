# FTIAS Linux Internal Deployment Guide

## Deployment Scope

This guide is for deploying FTIAS as an Internal Alpha / Technical Preview on a Linux server managed by the FTI team.

The deployment is intended for controlled FTI team review only. It is not production-certified and must not be treated as certification approval, operational authorization, airworthiness determination, flutter clearance, safety clearance, or loads substantiation.

FTIAS is engineering support software. Local IT/FTI approval is required before installation, network exposure, real dataset use, AI/API integration, or peer-review access.

## Questions for the FTI Server Team

Confirm these items before deployment:

- [ ] Is Docker allowed on the Linux server?
- [ ] Is Docker Compose available or permitted?
- [ ] What Linux distribution and version is used?
- [ ] Does the server have internet access?
- [ ] Can it access GitHub?
- [ ] Can it access container/package registries?
- [ ] Can it access external AI/API services, if needed?
- [ ] What internal ports can be exposed?
- [ ] What internal URL, hostname, or IP will users access?
- [ ] Can persistent Docker volumes be used?
- [ ] Who owns PostgreSQL backup/restore?
- [ ] Where should application data be stored?
- [ ] Are non-sensitive sample datasets allowed?
- [ ] Are real flight-test datasets allowed?
- [ ] Who will administer user accounts?
- [ ] What logging/monitoring restrictions apply?
- [ ] Is HTTPS required internally?
- [ ] Is there an approved reverse proxy, such as Nginx, Apache, or Traefik?

## Server Prerequisites

Recommended baseline:

- Linux server with shell access.
- Docker Engine.
- Docker Compose plugin.
- Git, if online clone or internal mirror clone is allowed.
- Disk capacity for PostgreSQL volume, uploaded files, reports, and logs.
- Network access from intended internal users.
- Firewall allowance for selected frontend/backend ports or reverse-proxy ports.
- Optional approved reverse proxy and internal HTTPS certificate.

Check the server:

```bash
docker --version
docker compose version
git --version
df -h
free -h
uname -a
```

If Docker or Docker Compose is missing, stop and coordinate with local IT. Do not install system packages without site approval.

## Recommended Deployment Shape

For internal alpha, the simplest deployment is Docker Compose on a single Linux host:

```text
Internal users -> FTI internal URL / IP -> frontend container
                                      -> backend container
                                      -> postgres container with persistent Docker volume
```

Default local service ports are:

- Frontend: `5173`
- Backend API: `8000`
- PostgreSQL: `5432`
- Optional pgAdmin: `5050`

For a shared internal server, prefer exposing only the frontend through an approved reverse proxy. Backend access should be limited to the frontend and trusted maintainers when possible.

## Repository Transfer Options

Choose one approved transfer path.

### Option A - Online Clone

Use this only if the server can access GitHub or an approved internal Git mirror:

```bash
git clone https://github.com/Martinolli/flight-test-interactive-analysis-suite.git
cd flight-test-interactive-analysis-suite
git checkout v0.1.0-alpha
```

If the tag is not available on the server, deploy from the approved release commit or internal mirror reference.

### Option B - ZIP Archive Transfer

Use this when GitHub is blocked but an internal file share, secure transfer, or removable media path is approved.

On a connected workstation, export a ZIP archive from the approved `v0.1.0-alpha` source tree. Transfer the ZIP through the approved internal path.

On the server:

```bash
unzip flight-test-interactive-analysis-suite.zip
cd flight-test-interactive-analysis-suite
```

If a tar archive is preferred by local IT, use the same approval process and extract it to the deployment directory.

Example source archive creation on a connected workstation:

```bash
git checkout v0.1.0-alpha
git archive --format=tar.gz --output ftias-v0.1.0-alpha-source.tar.gz v0.1.0-alpha
```

Example extraction on the server:

```bash
mkdir -p /opt/ftias
tar -xzf ftias-v0.1.0-alpha-source.tar.gz -C /opt/ftias
cd /opt/ftias
```

### Option C - Git Bundle Transfer

Use this when maintainers want commit history without direct network access.

On a connected workstation:

```bash
git bundle create ftias-v0.1.0-alpha.bundle --all
```

Transfer the bundle through an approved internal path.

On the server:

```bash
git clone ftias-v0.1.0-alpha.bundle flight-test-interactive-analysis-suite
cd flight-test-interactive-analysis-suite
git checkout v0.1.0-alpha
```

### Option D - Internal Mirror

If available, mirror the repository to an approved internal Git service. Use the internal mirror as the server clone source and document the mirror URL, release tag, and reviewed commit.

### Option E - Prebuilt Docker Image Transfer

Use this if the server cannot access container registries or package registries. This path requires a compatible build machine with Docker access.

On a connected build machine:

```bash
docker compose --profile frontend build
docker save -o ftias-backend.tar ftias-backend:latest
docker save -o ftias-frontend.tar ftias-frontend:latest
```

Image names may differ depending on Compose project naming. Confirm with:

```bash
docker images
```

Transfer image tarballs plus the repository source, `.env` template, and Compose files through an approved path.

On the server:

```bash
docker load -i ftias-backend.tar
docker load -i ftias-frontend.tar
```

If image names do not match the Compose build output, coordinate with the maintainer before starting services. Do not edit Compose files on the server unless the change is reviewed and recorded.

## Environment Configuration

Create the deployment environment file from the template if `.env.example` is present:

```bash
cp .env.example .env
```

If `.env.example` is not available in a transferred package, identify required variables from `docker-compose.yml` and current project documentation before starting the stack.

Edit `.env` with site-approved values:

```bash
nano .env
```

Minimum values to review:

```text
POSTGRES_DB=ftias_db
POSTGRES_USER=ftias_user
POSTGRES_PASSWORD=<site-approved-password>
POSTGRES_PORT=5432

BACKEND_PORT=8000
APP_ENV=internal-alpha
DEBUG=false
SECRET_KEY=<site-approved-random-secret>
JWT_SECRET_KEY=<site-approved-random-jwt-secret>
CORS_ORIGINS=http://<server-hostname-or-ip>:5173

FRONTEND_PORT=5173
VITE_API_URL=http://<server-hostname-or-ip>:8000
NODE_ENV=development
```

If an approved internal reverse proxy and HTTPS URL are used, set URLs accordingly:

```text
CORS_ORIGINS=https://<internal-ftias-hostname>
VITE_API_URL=https://<internal-ftias-hostname>
```

AI/RAG features require approved external or internal AI/API access. If external API access is not permitted, leave API keys unset and treat AI-backed workflows as unavailable or limited.

```text
OPENAI_API_KEY=
```

Deterministic/data workflows, upload, charts, FRAT, report review, and Manual / Help may still be useful without external AI access depending on deployment configuration.

Never commit `.env`, credentials, API keys, or real flight-test data.

## Start the Stack

From the repository root on the server:

```bash
docker compose config
docker compose up -d --build backend frontend
```

The current `docker-compose.yml` defines `postgres`, `backend`, and `frontend`. Starting `backend` and `frontend` should also start the required PostgreSQL dependency. If local policy requires explicit service names, use:

```bash
docker compose up -d --build postgres backend frontend
```

Check status:

```bash
docker compose ps
```

Expected internal alpha URLs, adjusted for server hostname/IP:

```text
Frontend: http://<server-hostname-or-ip>:5173
Backend docs: http://<server-hostname-or-ip>:8000/docs
```

Check `docker-compose.yml` for the current mapped ports before sharing URLs. If `.env` overrides `FRONTEND_PORT` or `BACKEND_PORT`, use the configured values.

Current note: the Compose frontend service runs the Vite development server for internal alpha convenience. This is acceptable for controlled technical review only. A hardened production frontend serving model should be designed before wider deployment.

## Internal URL and Port Guidance

For direct internal alpha access, the frontend URL is usually based on the mapped frontend port:

```text
http://<server-hostname-or-ip>:5173
```

The backend API docs, if exposed, are usually available at:

```text
http://<server-hostname-or-ip>:8000/docs
```

Avoid exposing the backend publicly. If sharing with peers beyond the immediate FTI maintainer group, use an approved internal reverse proxy and expose only the intended frontend URL where practical.

Keep `VITE_API_URL` and `CORS_ORIGINS` aligned with the URL users actually access.

## Online vs Restricted Server Operation

Online/full mode:

- Server can pull packages/images.
- Server can access GitHub or an internal Git mirror.
- Server may access AI/API services if approved.
- Full AI/RAG capability may be possible depending on approved keys and network policy.

Restricted/offline mode:

- Use ZIP archive, git bundle, internal mirror, or prebuilt Docker image transfer.
- AI/API calls may be unavailable.
- Deterministic workflows, upload, charts, FRAT, reports, and Manual / Help may still be reviewable depending on configuration.
- Document disabled capabilities before peer review so reviewers do not interpret missing AI/API access as an application defect.

## Database and Persistence

The default Compose stack uses Docker volumes:

- `postgres_data` for PostgreSQL.
- `backend_cache` for backend cache.
- `pgadmin_data` if pgAdmin is enabled.

Inspect volumes:

```bash
docker volume ls
docker volume inspect flight-test-interactive-analysis-suite_postgres_data
```

Volume names may vary by Compose project name.

## Migrations

When new SQL migration files are added under `backend/migrations/`, apply them to the running PostgreSQL container before relying on the related feature.

Apply migrations only when new migration files are introduced. Back up the database first. If no migration tracking table exists for the target deployment, record applied migration filenames manually with date, operator, and result.

PowerShell example:

```powershell
Get-Content backend/migrations/<migration_file>.sql -Raw | docker compose exec -T postgres sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

Linux shell equivalent:

```bash
cat backend/migrations/<migration_file>.sql | docker compose exec -T postgres sh -lc 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
```

## Backup and Restore

Assign PostgreSQL backup ownership before using real or sensitive data.

PostgreSQL data must use persistent Docker volumes. Do not delete volumes during normal updates. Back up before upgrades, migrations, or code changes that may alter data.

Generic backup example:

```bash
docker compose exec postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > ftias_backup_$(date +%Y%m%d).sql
```

Generic restore example:

```bash
cat ftias_backup_YYYYMMDD.sql | docker compose exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB"
```

Do not store backups containing real flight-test data outside approved storage.

## Firewall and Reverse Proxy

Direct internal-alpha exposure can use:

```text
http://<server-hostname-or-ip>:5173
http://<server-hostname-or-ip>:8000
```

For broader peer review, prefer an approved reverse proxy and HTTPS. Confirm:

- Internal hostname.
- TLS certificate source.
- Allowed inbound ports, typically `80` and/or `443`.
- Whether backend `/docs` should be exposed.
- Whether uploads are size-limited by proxy configuration.

Do not expose the stack publicly without security review.

## Health Checks and Smoke Test

Use these commands while validating the deployment:

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
```

After deployment, run a bounded smoke test:

1. Open the frontend from an internal workstation.
2. Register/login with an approved test account.
3. Create or select a flight test.
4. Upload a non-sensitive sample CSV.
5. Confirm dataset version creation.
6. Confirm Dashboard duration window updates.
7. Open Parameters and chart a channel.
8. Confirm the AI Analysis page/panel opens.
9. Run AI Analysis only if AI/API access is approved.
10. Confirm report export works if dependencies/API keys are configured.
11. Confirm demo event markers are clearly labeled if toggled.
12. Create and score a FRAT assessment.
13. Trigger or inspect a hard-stop/no-go scenario.
14. Export FRAT.
15. Open Manual / Help and confirm the manual PDF opens.

Record issues using the GitHub templates or the internal feedback process if GitHub is blocked.

## No-GitHub Feedback Collection

If GitHub Issues are blocked in the work environment, collect feedback internally and later mirror it into GitHub when permitted.

Minimum feedback fields:

- Reviewer name/role.
- Review date.
- Workflow reviewed.
- Steps to reproduce.
- Expected behavior.
- Actual behavior.
- Screenshot or log excerpt, if allowed.
- Dataset version ID or label, if relevant.
- Analysis job ID, if relevant.
- FRAT assessment ID, if relevant.
- Report/export file name, if relevant.
- Severity.
- Responsible-use concern flag.

Use `PEER_REVIEW_GUIDE.md` and `ISSUE_TRIAGE_GUIDE.md` as the structure even when GitHub is unavailable.

## Operational Boundaries

- Use non-sensitive sample data unless real data use is approved.
- Do not upload classified, export-controlled, proprietary, or operationally sensitive data without authorization.
- Do not treat AI/RAG output as authoritative.
- Do not treat deterministic outputs as certification-corrected unless explicitly implemented and reviewed.
- Do not treat FRAT output as organizational approval.
- Do not treat flutter support as flutter clearance.
- Do not treat vibration/load screening as structural substantiation.

## Stop, Update, and Restart

Stop services:

```bash
docker compose down
```

If Git is available:

```bash
git pull
docker compose up -d --build backend frontend
docker compose ps
```

If ZIP or bundle transfer is used:

1. Stop services if needed.
2. Back up the database.
3. Replace the code directory carefully.
4. Preserve `.env`.
5. Preserve Docker volumes.
6. Rebuild containers.

```bash
docker compose up -d --build backend frontend
docker compose ps
```

## Troubleshooting

| Symptom | Likely cause | Check |
| ------- | ------------ | ----- |
| Port unavailable | Another service is using the mapped port | Check `docker compose ps`, `ss -tulpn`, and selected `FRONTEND_PORT` / `BACKEND_PORT` values. |
| Docker permission denied | User is not allowed to access Docker socket | Coordinate with local IT; confirm approved Docker group or sudo policy. |
| Database not ready | PostgreSQL still starting or health check failing | Run `docker compose ps` and `docker compose logs -f postgres`. |
| Frontend cannot reach backend | `VITE_API_URL`, `CORS_ORIGINS`, firewall, or reverse proxy mismatch | Confirm the backend URL from the user workstation and check backend logs. |
| AI features fail | API key missing, network egress blocked, or external AI/API not approved | Confirm `.env`, server egress policy, and approved AI/API use. |
| PDF/report export fails | Backend error, missing data, report dependency issue, or blocked export state | Check backend logs and confirm the analysis/FRAT artifact is export-eligible. |
| Upload fails | File size/type, backend error, proxy upload limit, or disk issue | Check backend logs, proxy limits, upload file type, and `df -h`. |
| Disk full | PostgreSQL volume, uploads, reports, logs, or Docker cache consuming disk | Run `df -h`, `docker system df`, and review backup/log retention. |
| Permissions issue | File ownership or restricted deployment directory | Confirm ownership of deployment directory and Docker volume policy with IT. |
| Migrations not applied | New SQL migration files were not run against PostgreSQL | Review `backend/migrations/`, backup database, apply missing migrations, and record filenames. |
| Database data disappears after rebuild | Volume removed or Compose project name changed | Inspect Docker volumes and avoid destructive volume removal commands. |

## Security and Internal-Alpha Notes

- Use non-sensitive sample/test data first.
- Do not expose FTIAS to the public internet.
- Use internal network access only.
- Protect `.env`.
- Restrict user accounts.
- Confirm data retention and backup policy.
- Confirm AI/API data policy before enabling external services.
- Confirm MIT License and organizational suitability before redistribution.

## Pre-Share Checklist

- [ ] FTI/IT approval obtained.
- [ ] Deployment host and URL recorded.
- [ ] `.env` configured with non-default secrets.
- [ ] Data policy confirmed.
- [ ] Backup owner assigned.
- [ ] Manual smoke test completed.
- [ ] Responsible-use limitations communicated.
- [ ] Peer-review feedback path agreed.
- [ ] Known warnings documented.
- [ ] Deployment is limited to Internal Alpha / Technical Preview users.
