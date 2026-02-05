# Contributing to FTIAS

Thank you for your interest in contributing to the Flight Test Interactive Analysis Suite (FTIAS). This document provides guidelines and standards for contributing to the project.

---

## Table of Contents

1. [Development Environment Setup](#development-environment-setup)
2. [Git Workflow](#git-workflow)
3. [Coding Standards](#coding-standards)
4. [Testing Requirements](#testing-requirements)
5. [Pull Request Process](#pull-request-process)
6. [Code Review Guidelines](#code-review-guidelines)

---

## Development Environment Setup

### Prerequisites

- **Python 3.11+** for backend development
- **Node.js 18+** and **pnpm** for frontend development
- **Docker Desktop** for containerized development
- **PostgreSQL 15+** (via Docker or local installation)
- **Git** for version control
- **VSCode** (recommended IDE)

### Initial Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/Martinolli/flight-test-interactive-analysis-suite.git
   cd flight-test-interactive-analysis-suite
   ```

2. Install recommended VSCode extensions (see `.vscode/extensions.json`)

3. Start the development environment:

   ```bash
   docker-compose up
   ```

---

## Git Workflow

### Branch Strategy

We follow a **feature branch workflow**:

- `main` - Production-ready code (protected branch)
- `develop` - Integration branch for features (protected branch)
- `feature/*` - New features (e.g., `feature/parameter-browser`)
- `bugfix/*` - Bug fixes (e.g., `bugfix/chart-rendering`)
- `hotfix/*` - Critical production fixes
- `docs/*` - Documentation updates

### Branch Protection Rules

**Main Branch:**

- Requires pull request reviews (minimum 1 approval)
- Requires status checks to pass
- No direct commits allowed

**Develop Branch:**

- Requires pull request reviews
- Requires CI/CD pipeline to pass

### Commit Message Format

We follow the **Conventional Commits** specification:

```bash
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, no logic change)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks
- `perf`: Performance improvements

**Examples:**

```bash
feat(backend): add parameter search API endpoint

Implement /api/parameters/search endpoint with filtering
by name, description, and workgroup.

Closes #42
```

```bash
fix(frontend): resolve chart rendering issue on time filter

Fixed issue where chart would not update when time interval
slider was adjusted rapidly.

Fixes #58
```

### Creating a Feature Branch

```bash
# Update your local main branch
git checkout main
git pull origin main

# Create and checkout feature branch
git checkout -b feature/your-feature-name

# Make your changes and commit
git add .
git commit -m "feat(scope): description"

# Push to remote
git push origin feature/your-feature-name
```

---

## Coding Standards

### Python (Backend)

**Style Guide:** PEP 8

**Formatting:**

- Use **Black** for code formatting (line length: 100)
- Use **isort** for import sorting
- Use **flake8** for linting

**Type Hints:**

- All functions must have type hints
- Use `typing` module for complex types

**Example:**

```python
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ParameterResponse(BaseModel):
    """Response model for parameter data."""
    
    code: str
    description: str
    unit: Optional[str] = None


@router.get("/parameters", response_model=List[ParameterResponse])
async def get_parameters(
    search: Optional[str] = None,
    workgroup: Optional[str] = None
) -> List[ParameterResponse]:
    """
    Retrieve flight test parameters with optional filtering.
    
    Args:
        search: Optional search term for parameter name/description
        workgroup: Optional workgroup filter
        
    Returns:
        List of parameter objects matching the criteria
    """
    # Implementation here
    pass
```

**Naming Conventions:**

- Variables and functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`

**Documentation:**

- Use docstrings for all public functions and classes
- Follow Google-style docstring format

### TypeScript/React (Frontend)

**Style Guide:** Airbnb TypeScript Style Guide

**Formatting:**

- Use **Prettier** for code formatting
- Use **ESLint** for linting
- Indentation: 2 spaces

**Type Safety:**

- Avoid `any` type - use proper TypeScript types
- Define interfaces for all props and state
- Use strict mode

**Example:**

```typescript
import React, { useState, useEffect } from 'react';
import { useAppDispatch, useAppSelector } from '@/hooks/redux';
import { fetchParameters } from '@/store/slices/parametersSlice';

interface ParameterBrowserProps {
  onParameterSelect: (parameterId: string) => void;
  selectedWorkgroup?: string;
}

export const ParameterBrowser: React.FC<ParameterBrowserProps> = ({
  onParameterSelect,
  selectedWorkgroup,
}) => {
  const dispatch = useAppDispatch();
  const { parameters, loading, error } = useAppSelector((state) => state.parameters);
  const [searchTerm, setSearchTerm] = useState<string>('');

  useEffect(() => {
    dispatch(fetchParameters({ search: searchTerm, workgroup: selectedWorkgroup }));
  }, [dispatch, searchTerm, selectedWorkgroup]);

  if (loading) return <LoadingSpinner />;
  if (error) return <ErrorMessage message={error} />;

  return (
    <div className="parameter-browser">
      {/* Component implementation */}
    </div>
  );
};
```

**Naming Conventions:**

- Components: `PascalCase` (e.g., `ParameterBrowser.tsx`)
- Hooks: `camelCase` with `use` prefix (e.g., `useParameters`)
- Utilities: `camelCase` (e.g., `formatDate`)
- Constants: `UPPER_SNAKE_CASE`

**Component Structure:**

```bash
ComponentName/
├── index.ts              # Public exports
├── ComponentName.tsx     # Main component
├── ComponentName.test.tsx # Tests
├── ComponentName.styles.ts # Styled components (if using)
└── types.ts              # Component-specific types
```

### SQL (Database)

**Naming Conventions:**

- Tables: `snake_case`, plural (e.g., `flight_parameters`)
- Columns: `snake_case` (e.g., `created_at`)
- Indexes: `idx_<table>_<column>` (e.g., `idx_parameters_code`)
- Foreign keys: `fk_<table>_<referenced_table>` (e.g., `fk_flights_users`)

**Best Practices:**

- Always use migrations for schema changes
- Include rollback scripts
- Add comments for complex queries
- Use transactions for multi-step operations

---

## Testing Requirements

### Backend Testing

**Framework:** pytest

**Coverage Requirements:**

- Minimum 80% code coverage for new code
- 100% coverage for critical business logic

**Test Structure:**

```bash
tests/
├── unit/              # Unit tests
├── integration/       # Integration tests
└── conftest.py        # Shared fixtures
```

**Example:**

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_parameters_success():
    """Test successful parameter retrieval."""
    response = client.get("/api/parameters")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_parameters_with_filter():
    """Test parameter retrieval with workgroup filter."""
    response = client.get("/api/parameters?workgroup=ENGINE")
    assert response.status_code == 200
    data = response.json()
    assert all(p["workgroup"] == "ENGINE" for p in data)
```

### Frontend Testing

**Framework:** Jest + React Testing Library

**Coverage Requirements:**

- Minimum 70% code coverage for new components
- All user interactions must be tested

**Example:**

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { ParameterBrowser } from './ParameterBrowser';

describe('ParameterBrowser', () => {
  it('renders parameter list', () => {
    render(<ParameterBrowser onParameterSelect={jest.fn()} />);
    expect(screen.getByText('Parameters')).toBeInTheDocument();
  });

  it('calls onParameterSelect when parameter is clicked', () => {
    const mockSelect = jest.fn();
    render(<ParameterBrowser onParameterSelect={mockSelect} />);
    
    const parameter = screen.getByText('ALT_MSL');
    fireEvent.click(parameter);
    
    expect(mockSelect).toHaveBeenCalledWith('ALT_MSL');
  });
});
```

### Running Tests

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
pnpm test

# All tests with coverage
pnpm test:coverage
```

---

## Pull Request Process

### Before Creating a PR

1. **Ensure all tests pass:**

   ```bash
   pnpm test
   ```

2. **Run linters and formatters:**

   ```bash
   pnpm lint
   pnpm format
   ```

3. **Update documentation** if needed

4. **Rebase on latest main:**

   ```bash
   git checkout main
   git pull origin main
   git checkout feature/your-feature
   git rebase main
   ```

### PR Template

When creating a pull request, include:

**Title:** Follow commit message format

**Description:**

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests pass locally

## Related Issues
Closes #(issue number)

## Screenshots (if applicable)
```

### PR Review Process

1. **Automated Checks:** CI/CD pipeline must pass
2. **Code Review:** At least one approval required
3. **Testing:** Reviewer should test functionality locally
4. **Merge:** Squash and merge to maintain clean history

---

## Code Review Guidelines

### For Authors

- Keep PRs small and focused (< 400 lines of code)
- Provide context in PR description
- Respond to feedback promptly
- Be open to suggestions

### For Reviewers

**What to Look For:**

1. **Correctness:** Does the code do what it's supposed to?
2. **Design:** Is the code well-structured and maintainable?
3. **Complexity:** Is the code as simple as possible?
4. **Tests:** Are there adequate tests?
5. **Naming:** Are variables and functions well-named?
6. **Comments:** Are comments clear and necessary?
7. **Documentation:** Is documentation updated?
8. **Security:** Are there any security concerns?

**Review Etiquette:**

- Be respectful and constructive
- Explain the "why" behind suggestions
- Distinguish between required changes and suggestions
- Approve when ready, even if minor suggestions remain

**Example Comments:**

✅ Good:

```bash
Consider extracting this logic into a separate function for reusability.
This would make the code more maintainable and easier to test.
```

❌ Avoid:

```bash
This is wrong. Fix it.
```

---

## Questions or Issues?

If you have questions about contributing:

1. Check existing documentation in `/docs`
2. Search existing GitHub issues
3. Create a new issue with the `question` label
4. Reach out to the project maintainers

---

**Thank you for contributing to FTIAS!** 🚀
