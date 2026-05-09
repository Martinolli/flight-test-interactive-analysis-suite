# FTIAS GitHub Actions Workflows

This README documents GitHub Actions workflows. For the main project overview, see ../README.md.

If this file is displayed while browsing the `.github` directory, return to the repository root to view the main README.

## Workflow Inventory

### `backend-lint.yml` - Backend Linting

Triggers:

- `push` to `main` or `develop` when `backend/**` or `.github/workflows/backend-lint.yml` changes.
- `pull_request` to `main` or `develop` when `backend/**` changes.

Validates:

- Black formatting for `backend/app/`.
- isort import ordering for `backend/app/`.
- Flake8 linting for `backend/app/`.

Notes:

- This workflow is path-filtered. Documentation-only commits normally do not trigger it.
- Flake8 settings live in `backend/.flake8`.

### `backend-test.yml` - Backend Tests

Triggers:

- `push` to `main` or `develop`.
- `pull_request` to `main` or `develop`.

Validates:

- Backend pytest suite with a PostgreSQL service container.
- Coverage XML and HTML generation inside the CI job.
- Codecov upload from `backend/coverage.xml`.

Notes:

- This workflow is not path-filtered, so it may run for documentation-only commits.
- Local coverage artifacts such as `.coverage`, `coverage.xml`, and `htmlcov/` are generated files and should not be committed.

### `docker-build.yml` - Docker Build Validation

Triggers:

- `push` to `main` or `develop` when `docker/**`, `docker-compose.yml`, `backend/**`, or `.github/workflows/docker-build.yml` changes.
- `pull_request` to `main` or `develop` when `docker/**`, `docker-compose.yml`, or `backend/**` changes.

Validates:

- `docker-compose.yml` syntax.
- `docker-compose.backend-only.yml` syntax.
- Backend Docker image build using `docker/backend.Dockerfile`.

Notes:

- This workflow is path-filtered. Documentation-only commits normally do not trigger it.

## Expected Status Checks

For backend or Docker code changes, expected checks are:

- Backend Linting
- Backend Tests
- Docker Build Validation, when Docker/backend paths match the workflow filter

For documentation-only changes, GitHub Actions may show only a subset of checks because some workflows are path-filtered.

Frontend build validation is currently expected as a local maintainer check:

```powershell
pnpm -C frontend run build
```

## Local Validation Commands

Run these from the repository root:

```powershell
black --check --diff backend/app backend/tests
pytest backend/tests -q
pnpm -C frontend run build
```

Useful Docker validation:

```powershell
docker compose -f docker-compose.yml config
docker compose -f docker-compose.backend-only.yml config
docker compose up -d --build backend frontend
```

## Configuration Files

- `backend/.flake8` - Flake8 configuration; max complexity is currently `40`.
- `backend/pyproject.toml` - Black and isort configuration.
- `backend/pytest.ini` - Backend pytest configuration.
- `.github/workflows/*.yml` - GitHub Actions workflow definitions.

## Known Build Warnings

- Frontend builds may warn that Node.js `20.18.1` is installed while Vite expects `20.19+` or `22.12+`.
- Frontend builds may warn that some chunks are larger than 500 kB after minification.

Both warnings are documented for internal alpha. They should be revisited before wider release.

## Repository Hygiene

- Keep generated coverage files out of commits: `.coverage`, `coverage.xml`, and `htmlcov/`.
- Keep frontend build/cache output out of commits: `frontend/dist/`, `frontend/node_modules/`, and `frontend/.vite/`.
- Keep local environment files and logs out of commits.
- Before sharing an alpha branch, confirm `git status` shows only intentional changes.
