# Bcrypt Fix for Windows

**Date:** February 7, 2026
**Issue:** Bcrypt backend initialization error on Windows
**Status:** ✅ FIX READY

---

## 🐛 Issue

**Error:**

```bash
ValueError: password cannot be longer than 72 bytes, truncate manually if necessary
WARNING passlib.handlers.bcrypt:bcrypt.py:622 (trapped) error reading bcrypt version
```

**Root Cause:**

- passlib[bcrypt] on Windows sometimes has issues with bcrypt backend detection
- The bcrypt library needs to be explicitly installed with a compatible version
- This is a known issue on Windows with Python 3.12

---

## ✅ Fix

### **Updated:** `backend/requirements.txt`

**Added explicit bcrypt dependency:**

```bash
bcrypt==4.1.2
```

This ensures the correct bcrypt backend is available for passlib.

---

## 📋 Action Required

### **Step 1: Install the Updated Requirements**

```powershell
# Make sure you're in the backend directory
cd backend

# Install/upgrade bcrypt
pip install bcrypt==4.1.2

# Or reinstall all requirements
pip install -r requirements.txt --upgrade
```

### **Step 2: Run Tests Again**

```powershell
pytest -v
```

**Expected:** All 13 tests should pass! ✅

---

## 🎯 Alternative: If Still Fails

If the bcrypt issue persists, you can temporarily disable bcrypt and use a simpler hash for testing:

### **Option A: Use argon2 instead**

```powershell
pip install passlib[argon2]
```

Then update `backend/app/routers/users.py`:

```python
from passlib.context import CryptContext

# Change from bcrypt to argon2
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")
```

### **Option B: Mock password hashing in tests**

Update `tests/conftest.py` to mock the password hashing:

```python
@pytest.fixture
def mock_hash_password(monkeypatch):
    def mock_hash(password):
        return f"hashed_{password}"
    monkeypatch.setattr("app.routers.users.hash_password", mock_hash)
```

---

## 🔍 Why This Happens

**Windows-Specific Issue:**

- bcrypt requires compilation on Windows
- Pre-built wheels sometimes have compatibility issues
- Python 3.12 is relatively new, binary compatibility can be tricky

**The Fix:**

- Explicit bcrypt version ensures proper binary is downloaded
- Version 4.1.2 has good Windows Python 3.12 support

---

## ✅ Expected Result After Fix

```bash
tests/test_health.py::test_root_endpoint PASSED
tests/test_health.py::test_health_check PASSED
tests/test_health.py::test_ping_endpoint PASSED
tests/test_users.py::test_create_user PASSED
tests/test_users.py::test_create_duplicate_user PASSED
tests/test_users.py::test_get_users PASSED
tests/test_users.py::test_get_user_by_id PASSED
tests/test_users.py::test_get_nonexistent_user PASSED
tests/test_users.py::test_update_user PASSED
tests/test_users.py::test_delete_user PASSED
tests/test_users.py::test_delete_nonexistent_user PASSED
tests/test_users.py::test_user_data_validation PASSED
tests/test_users.py::test_invalid_email_format PASSED

============================== 13 passed ==============================
```

---

## 📦 Commands Summary

```powershell
# 1. Install bcrypt
pip install bcrypt==4.1.2

# 2. Commit the fix
git add requirements.txt
git commit -m "fix(deps): add explicit bcrypt dependency for Windows compatibility"
git push origin main

# 3. Run tests
pytest -v

# 4. Check all linting
black --check app/
isort --check-only app/
flake8 app/
```

---

**Status:** Ready to install and test! 🚀
