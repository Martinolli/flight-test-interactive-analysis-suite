# Sprint 1 Implementation Guide - Windows/VSCode Setup

**Sprint:** 1 (Weeks 1-2)
**Goal:** Project Setup and Environment Configuration
**Platform:** Windows with VSCode

---

## Current Repository Status

✅ **Already Complete:**

- Git repository initialized and synced with GitHub
- Project documentation (README, Requirements Review, Implementation Plan)
- Basic `.gitignore` and `.gitattributes` configured
- Python virtual environment (`.venv`) created

---

## Sprint 1 Tasks - Step by Step

### **Task 1.1: Repository Structure and Branch Policies**

**What we'll do:**

1. Create the project directory structure
2. Set up branch protection rules on GitHub
3. Configure Git workflow for the team

**Steps:**

#### Step 1.1.1: Create Project Directory Structure

Create the following folders in your local repository:

```bash
ftias-project/
├── backend/          # FastAPI backend application
├── frontend/         # React frontend application
├── database/         # Database scripts and migrations
├── docker/           # Docker configuration files
├── tests/            # Test files
├── docs/             # Documentation (already exists)
└── scripts/          # Utility scripts
```

**Action for you:** In your Windows terminal (PowerShell or CMD) in the project root:

```powershell
mkdir backend, frontend, database, docker, tests, scripts
```

**Expected Result:** Seven directories created in your project root.

---

### **Task 1.2: Project Management Setup**

**What we'll do:**

1. Create a `CONTRIBUTING.md` file with coding standards
2. Set up issue templates for GitHub
3. Create initial project board

**Steps:**

#### Step 1.2.1: Create CONTRIBUTING.md

This file will be created with:

- Coding standards (Python PEP 8, TypeScript/React best practices)
- Git workflow (feature branches, commit message format)
- Pull request process
- Code review guidelines

**Action for you:** Review and approve the CONTRIBUTING.md file I'll create.

---

### **Task 1.3: Docker Environment Setup**

**What we'll do:**

1. Create `docker-compose.yml` for local development
2. Create Dockerfiles for backend and frontend
3. Set up PostgreSQL container
4. Test that everything starts with one command

**Prerequisites for Windows:**

- Docker Desktop for Windows installed
- WSL2 enabled (recommended)

**Do you have Docker Desktop installed?** (We'll verify before proceeding)

---

### **Task 1.4: VSCode Configuration**

**What we'll do:**

1. Create `.vscode/settings.json` with recommended settings
2. Create `.vscode/extensions.json` with recommended extensions
3. Configure linters and formatters
4. Set up debugging configurations

**Recommended Extensions:**

- Python (Microsoft)
- Pylance
- ESLint
- Prettier
- Docker
- GitLens
- Thunder Client (API testing)

---

### **Task 1.5: CI/CD Pipeline Foundation**

**What we'll do:**

1. Create `.github/workflows/ci.yml` for automated testing
2. Configure linting and formatting checks
3. Set up automated tests to run on pull requests

---

## Checkpoint Questions Before We Start

Before we begin implementation, please confirm:

1. **Do you have Docker Desktop installed on Windows?** (Yes/No)
2. **Do you have Node.js installed?** (Check with `node --version` in terminal)
3. **Do you have Python installed?** (Check with `python --version`)
4. **Are you comfortable with PowerShell or do you prefer CMD?**
5. **Would you like me to create all files first, then you review, or go one-by-one?**

Please answer these questions so I can tailor the implementation to your setup!
