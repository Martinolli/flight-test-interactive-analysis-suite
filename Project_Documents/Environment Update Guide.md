# Environment Update Guide

**Date:** February 8, 2026
**Issue:** Installing new dependencies from backend/requirements.txt

---

## The Situation

Your project structure:

```bash
flight-test-interactive-analysis-suite/
├── .venv/                    ← Virtual environment (root)
├── backend/
│   ├── requirements.txt      ← Dependencies here
│   └── app/
└── ...
```

When we add new dependencies to `backend/requirements.txt`, you need to install them in your `.venv`.

---

## Solution: Install from backend/requirements.txt

### **Option 1: Install from backend folder (Recommended)**

```powershell
# Make sure you're in the project root with .venv activated
cd C:\Users\Aspire5 15 i7 4G2050\flight-test-interactive-analysis-suite

# Activate virtual environment (if not already)
.venv\Scripts\activate

# Install from backend/requirements.txt
pip install -r backend/requirements.txt
```

### **Option 2: Navigate to backend folder**

```powershell
# From project root
cd backend

# Install requirements
pip install -r requirements.txt

# Go back to root
cd ..
```

### **Option 3: Install specific package only**

If you just want to install the new package (openpyxl):

```powershell
# From project root with .venv activated
pip install openpyxl==3.1.2
```

---

## Verify Installation

After installing, verify the package is available:

```powershell
# Check if openpyxl is installed
pip show openpyxl

# Or list all installed packages
pip list | Select-String openpyxl
```

---

## Docker Environment

**Important:** The Docker containers have their own Python environment!

When you run `docker-compose up --build`, Docker will:

1. Read `backend/requirements.txt`
2. Install all dependencies inside the container
3. Use the container's Python environment (not your local .venv)

So for Docker, you don't need to do anything - it handles dependencies automatically during build.

---

## Summary

**For local development (pytest, black, etc.):**

```powershell
# From project root
.venv\Scripts\activate
pip install -r backend/requirements.txt
```

**For Docker:**

```powershell
# Docker handles it automatically
docker-compose up --build
```

---

## Current New Dependency

We just added:

- `openpyxl==3.1.2` - For reading Excel files (985 parameters)

**Install it now:**

```powershell
pip install openpyxl==3.1.2
```

Or install everything:

```powershell
pip install -r backend/requirements.txt
```

---

**Ready to proceed once you've installed the dependencies!** ✅
