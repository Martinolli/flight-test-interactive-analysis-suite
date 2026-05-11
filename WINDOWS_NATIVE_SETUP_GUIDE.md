# FTIAS Windows Native Setup Guide

## Setup Scope

This guide is for running FTIAS on a Windows machine for Internal Alpha / Technical Preview review when Docker is not approved by IT.

This is not production deployment guidance. FTIAS is engineering support software only. It is not certification approval, operational authorization, airworthiness determination, flutter clearance, safety clearance, or loads substantiation.

Installing software, opening local ports, using external AI/API services, and storing flight-test data all require local IT/FTI approval.

## Questions for IT / FTI Support

Confirm these items before setup:

- [ ] Can Python 3.12 be installed?
- [ ] Can Node.js LTS be installed?
- [ ] Can npm/pnpm be used?
- [ ] Can PostgreSQL be installed locally or accessed from a managed server?
- [ ] Is pgvector available or allowed?
- [ ] Can Git be used?
- [ ] Are outbound calls to OpenAI/API services allowed?
- [ ] Are local ports `8000` and `5173` allowed?
- [ ] Can environment variables / `.env` files be used?
- [ ] Where should local database/data files be stored?
- [ ] Are non-sensitive sample datasets allowed?
- [ ] Are real flight-test datasets allowed?
- [ ] What backup/data retention policy applies?
- [ ] Is antivirus allowed to scan project folders or should exclusions be requested?

## Required Tools

Recommended baseline:

- Windows 10/11.
- Git for Windows.
- Python 3.12.
- Node.js LTS, preferably Node `20.19+` or `22.12+` to satisfy current Vite expectations.
- pnpm.
- PostgreSQL 15 or compatible PostgreSQL server.
- pgvector extension if document/RAG vector search is used.
- Optional: VS Code.

Check installed tools from PowerShell:

```powershell
git --version
python --version
pip --version
node --version
npm --version
pnpm --version
psql --version
```

If a required command is missing, stop and coordinate with IT before installing software.

## Repository Clone

Clone the repository:

```powershell
git clone https://github.com/Martinolli/flight-test-interactive-analysis-suite.git
cd flight-test-interactive-analysis-suite
```

To test the published alpha tag:

```powershell
git checkout v0.1.0-alpha
```

To test the latest internal-alpha documentation and changes, use the current `main` branch instead.

## Backend Setup

Create and activate a Python virtual environment:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks virtual environment activation, IT may need to allow script execution. Only if approved by IT, the current user can run:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Return to the repository root when finished:

```powershell
cd ..
```

## Frontend Setup

Install frontend dependencies and validate the build:

```powershell
cd frontend
pnpm install
pnpm run build
pnpm run dev
```

If pnpm is not installed and IT approves global npm installs:

```powershell
npm install -g pnpm
```

Known warning: Node `20.18.1` may be too low for the current Vite requirement. Prefer Node `20.19+` or `22.12+`.

Return to the repository root when finished:

```powershell
cd ..
```

## PostgreSQL Setup

FTIAS expects PostgreSQL for normal operation. Document/RAG vector search uses pgvector-backed embeddings.

### Option A - Local PostgreSQL on Windows

Use this if IT approves a local PostgreSQL installation.

Example using command-line tools:

```powershell
createdb ftias_db
```

Example using `psql` as a PostgreSQL administrator:

```sql
CREATE USER ftias_user WITH PASSWORD 'change-this-password';
CREATE DATABASE ftias_db OWNER ftias_user;
\c ftias_db
CREATE EXTENSION IF NOT EXISTS vector;
```

The `vector` extension is required for document embedding/RAG vector search. If the extension is unavailable, coordinate with IT before using document/RAG workflows.

### Option B - Managed PostgreSQL from IT

Use this if IT provides a managed PostgreSQL server. Request:

- Hostname.
- Port.
- Database name.
- Username/password or approved authentication method.
- Confirmation that pgvector is installed/enabled if document/RAG features are required.
- Backup/restore ownership.

### Option C - Restricted Mode

If PostgreSQL or pgvector is unavailable, the full app may not run correctly. Coordinate with IT for a managed PostgreSQL database or approved local installation.

Some deterministic/data workflows may still be useful once the core database is available, but document/RAG vector features should be treated as unavailable until pgvector and AI/API access are approved.

## `.env` Setup

Create a local environment file:

```powershell
copy .env.example .env
notepad .env
```

Review these values:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_PORT`
- `BACKEND_PORT`
- `FRONTEND_PORT`
- `VITE_API_URL`
- `CORS_ORIGINS`
- `SECRET_KEY`
- `JWT_SECRET_KEY`
- `OPENAI_API_KEY`
- `EMBEDDING_MODEL`

For local Windows defaults:

```text
BACKEND_PORT=8000
FRONTEND_PORT=5173
VITE_API_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:5173
```

Use strong local placeholder secrets for `SECRET_KEY` and `JWT_SECRET_KEY`. Do not commit `.env`.

If OpenAI/API access is not approved, leave:

```text
OPENAI_API_KEY=
```

`EMBEDDING_MODEL` should remain aligned with backend vector dimensions. The current expected value is:

```text
EMBEDDING_MODEL=text-embedding-3-small
```

## Migrations

Apply migrations only when needed, back up first, and record applied migration filenames if no migration tracker exists.

PowerShell example for native PostgreSQL:

```powershell
Get-Content backend\migrations\<migration_file>.sql -Raw | psql -U ftias_user -d ftias_db -v ON_ERROR_STOP=1
```

If using a managed PostgreSQL host, include the host and port approved by IT:

```powershell
Get-Content backend\migrations\<migration_file>.sql -Raw | psql -h <db-host> -p <db-port> -U ftias_user -d ftias_db -v ON_ERROR_STOP=1
```

## Run FTIAS

Start the backend from one PowerShell window:

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Start the frontend from a second PowerShell window:

```powershell
cd frontend
pnpm run dev -- --host 127.0.0.1 --port 5173
```

Access:

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs

## Smoke Test

Run a bounded internal-alpha smoke test:

- [ ] Backend docs open.
- [ ] Frontend opens.
- [ ] Login/register works.
- [ ] Manual / Help opens.
- [ ] Upload a non-sensitive CSV.
- [ ] Dataset version appears.
- [ ] Dashboard duration window updates.
- [ ] Parameters chart opens.
- [ ] AI Analysis opens.
- [ ] Report export works if dependencies/API key are configured.
- [ ] FRAT opens.
- [ ] FRAT score works.
- [ ] FRAT export works.

Record issues using `PEER_REVIEW_GUIDE.md` and `ISSUE_TRIAGE_GUIDE.md`.

## Restricted Operation

If OpenAI/API access is not approved:

- Leave `OPENAI_API_KEY` blank.
- AI/RAG features may fail or be unavailable.
- Deterministic/data workflows, charts, FRAT, Manual / Help, and some report workflows may still be testable depending on app behavior.
- Document disabled capabilities before peer review.

If PostgreSQL/pgvector is unavailable:

- The full app may not run correctly.
- Coordinate with IT for managed PostgreSQL or approved local install.
- Treat document/RAG vector workflows as unavailable until pgvector is enabled.

## Troubleshooting

| Symptom | Likely cause | Check |
| --- | --- | --- |
| Python not recognized | Python not installed or not on `PATH` | Run `py --version`; confirm Python 3.12 install with IT. |
| Virtual environment activation blocked | PowerShell execution policy | Ask IT to approve activation or `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. |
| `pip install` fails | Network/proxy/certificate restriction or compiler dependency | Check IT proxy rules, Python version, and package index access. |
| Node/npm/pnpm unavailable | Node.js or pnpm not installed | Confirm Node LTS install and `npm install -g pnpm` approval. |
| Vite Node version warning | Node version below current Vite requirement | Install approved Node `20.19+` or `22.12+`. |
| PostgreSQL connection refused | Database not running or wrong host/port | Check PostgreSQL service, `.env`, `psql`, and firewall rules. |
| pgvector/vector extension missing | pgvector not installed/enabled | Run `CREATE EXTENSION IF NOT EXISTS vector;` if approved, or request IT support. |
| Port `8000` or `5173` already in use | Another local service is using the port | Use `netstat -ano | findstr :8000` or `:5173`; coordinate before changing ports. |
| Frontend cannot reach backend | `VITE_API_URL` or CORS mismatch | Confirm backend is running at `http://localhost:8000` and `CORS_ORIGINS` includes frontend URL. |
| OpenAI/API features fail | API key missing or outbound access blocked | Confirm `OPENAI_API_KEY`, approved model access, and IT egress policy. |
| PDF/report export fails | Backend error, missing data, or export dependency issue | Check backend terminal logs and artifact eligibility. |
| Upload fails | File type/size, database issue, or backend error | Check backend logs, CSV format, `MAX_UPLOAD_SIZE`, and database connectivity. |
| Antivirus blocks files or slows install | Security scanning project, venv, node_modules, or package cache | Ask IT whether exclusions are allowed for approved project folders. |

## Security and Responsible Use

- Use non-sensitive sample/test data first.
- Do not commit `.env`.
- Do not commit real secrets, API keys, or local database dumps.
- Confirm data retention and backup policy before using real datasets.
- Confirm AI/API data policy before enabling external services.
- Restrict access to approved reviewers only.
- Keep responsible-use boundaries visible during peer review.
