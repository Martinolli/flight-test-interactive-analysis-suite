# FTIAS CI/CD Workflows

This directory contains GitHub Actions workflows for continuous integration and deployment.

---

## 📋 Workflows

### 1. **Backend Linting** (`backend-lint.yml`)

**Triggers:**

- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Changes in `backend/` directory

**Checks:**

- **Black:** Code formatting (PEP 8 compliant)
- **isort:** Import statement sorting
- **Flake8:** Code quality and style

**Configuration:**

- `.flake8` - Flake8 rules
- `pyproject.toml` - Black and isort settings

---

### 2. **Backend Testing** (`backend-test.yml`)

**Triggers:**

- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Changes in `backend/` directory

**Features:**

- Runs pytest test suite
- PostgreSQL service container for integration tests
- Code coverage reporting
- Uploads coverage to Codecov (optional)

**Test Database:**

- PostgreSQL 15 Alpine
- Isolated test database per run
- Health checks before tests

**Configuration:**

- `pytest.ini` - Pytest settings
- `conftest.py` - Test fixtures

---

### 3. **Docker Build Validation** (`docker-build.yml`)

**Triggers:**

- Push to `main` or `develop` branches
- Pull requests to `main` or `develop`
- Changes in `docker/`, `docker-compose.yml`, or `backend/`

**Checks:**

- Validates docker-compose.yml syntax
- Validates docker-compose.backend-only.yml
- Builds backend Docker image
- Uses build cache for faster builds

---

## 🚀 Running Tests Locally

### **Linting**

```bash
cd backend

# Run Black (formatter check)
black --check app/

# Run Black (auto-format)
black app/

# Run isort (import sorting check)
isort --check-only app/

# Run isort (auto-sort)
isort app/

# Run Flake8 (linter)
flake8 app/
```

### **Testing**

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/test_health.py

# Run specific test
pytest tests/test_users.py::test_create_user

# Run tests with markers
pytest -m api          # Only API tests
pytest -m database     # Only database tests
pytest -m unit         # Only unit tests
```

### **Docker Build**

```bash
# Validate docker-compose
docker compose -f docker-compose.yml config

# Build backend image
docker build -f docker/backend.Dockerfile -t ftias-backend:test .

# Build with docker-compose
docker-compose build backend
```

---

## 📊 Test Markers

Tests are organized with pytest markers:

- `@pytest.mark.unit` - Unit tests (fast, no external dependencies)
- `@pytest.mark.integration` - Integration tests (database, external services)
- `@pytest.mark.api` - API endpoint tests
- `@pytest.mark.database` - Database tests
- `@pytest.mark.slow` - Slow running tests

**Example:**

```python
@pytest.mark.api
@pytest.mark.database
def test_create_user(client, sample_user_data):
    # Test code here
    pass
```

---

## 🔧 Configuration Files

### **Backend Directory:**

```bash
backend/
├── .flake8              # Flake8 linter configuration
├── pytest.ini           # Pytest configuration
├── pyproject.toml       # Black and isort configuration
└── tests/
    ├── __init__.py
    ├── conftest.py      # Pytest fixtures
    ├── test_health.py   # Health endpoint tests
    └── test_users.py    # User endpoint tests
```

---

## 🎯 Code Quality Standards

### **Black (Code Formatting)**

- Line length: 100 characters
- Python 3.12 target
- PEP 8 compliant

### **isort (Import Sorting)**

- Profile: Black-compatible
- Multi-line output: 3
- Trailing commas: Yes

### **Flake8 (Linting)**

- Max line length: 100
- Max complexity: 10
- Ignores: E203, W503 (Black compatibility)

---

## 📈 Coverage Reports

After running tests with coverage:

```bash
# View in terminal
pytest --cov=app --cov-report=term-missing

# Generate HTML report
pytest --cov=app --cov-report=html
# Open: htmlcov/index.html

# Generate XML report (for CI)
pytest --cov=app --cov-report=xml
```

---

## 🚨 Workflow Status Badges

Add these to your README.md:

```markdown
![Backend Linting](https://github.com/Martinolli/flight-test-interactive-analysis-suite/workflows/Backend%20Linting/badge.svg)
![Backend Testing](https://github.com/Martinolli/flight-test-interactive-analysis-suite/workflows/Backend%20Testing/badge.svg)
![Docker Build](https://github.com/Martinolli/flight-test-interactive-analysis-suite/workflows/Docker%20Build%20Validation/badge.svg)
```

---

## 🔄 Workflow Triggers

All workflows trigger on:

- **Push** to `main` or `develop`
- **Pull Request** to `main` or `develop`
- Only when relevant files change

This ensures:

- Fast feedback on code changes
- No unnecessary workflow runs
- Efficient use of GitHub Actions minutes

---

## 💡 Best Practices

1. **Run tests locally before pushing**

   ```bash
   cd backend && pytest && black --check app/ && flake8 app/
   ```

2. **Fix linting issues automatically**

   ```bash
   cd backend && black app/ && isort app/
   ```

3. **Check coverage before committing**

   ```bash
   cd backend && pytest --cov=app --cov-report=term-missing
   ```

4. **Use test markers for focused testing**

   ```bash
   pytest -m "api and not slow"
   ```

---

## 📝 Adding New Tests

1. Create test file in `backend/tests/`
2. Name file `test_*.py`
3. Use fixtures from `conftest.py`
4. Add appropriate markers
5. Run tests locally
6. Commit and push

**Example:**

```python
import pytest
from fastapi import status

@pytest.mark.api
def test_new_endpoint(client):
    response = client.get("/api/new-endpoint")
    assert response.status_code == status.HTTP_200_OK
```

---

## 🛠️ Troubleshooting

### **Tests failing locally but passing in CI**

- Check Python version (should be 3.12)
- Check database connection
- Clear pytest cache: `pytest --cache-clear`

### **Linting errors**

- Run Black: `black app/`
- Run isort: `isort app/`
- Check `.flake8` for ignored rules

### **Docker build failing**

- Validate compose file: `docker compose config`
- Check Dockerfile syntax
- Verify build context

---

## 📚 Resources

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Pytest Documentation](https://docs.pytest.org/)
- [Black Documentation](https://black.readthedocs.io/)
- [Flake8 Documentation](https://flake8.pycqa.org/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)

---

**CI/CD Pipeline Status:** ✅ Active and Running
