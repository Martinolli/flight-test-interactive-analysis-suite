# Step-by-Step Setup Guide - Complete Instructions

Follow these steps **exactly** to set up and run the Flight Test application locally.

---

## 📋 What You'll Need

- Your existing backend repository: `flight-test-interactive-analysis-suite`
- The frontend files from Manus (you'll download these)
- About 30 minutes to complete the setup

---

## Part 1: Local Development Setup

### **Step 1: Download the Frontend Files**

1. In the Manus interface, click on the checkpoint card
2. Click "Download" to get a ZIP file containing all frontend files
3. Extract the ZIP file to a temporary folder on your computer
4. You should see folders like: `client/`, `server/`, `drizzle/`, and files like `package.json`

---

### **Step 2: Copy Frontend to Your Repository**

1. Open your existing repository folder: `flight-test-interactive-analysis-suite`

2. **Delete the old frontend folder** (it only has `.dockerignore` and `.gitkeep`):

   ```bash
   # On Windows (PowerShell)
   Remove-Item -Recurse -Force frontend

   # On Mac/Linux
   rm -rf frontend
   ```

3. **Copy the new frontend folder** from the extracted ZIP into your repository:

   ```bash
   flight-test-interactive-analysis-suite/
   ├── backend/              (your existing backend)
   ├── frontend/             (NEW - copy here)
   │   ├── client/
   │   ├── server/
   │   ├── drizzle/
   │   ├── package.json
   │   └── ... (other files)
   ├── database/
   ├── docker/
   └── ... (other folders)
   ```

---

### **Step 3: Install Frontend Dependencies**

1. Open a terminal/command prompt

2. Navigate to the frontend folder:

   ```bash
   cd flight-test-interactive-analysis-suite/frontend
   ```

3. Install dependencies:

   ```bash
   pnpm install
   ```

   **Don't have pnpm?** Install it first:

   ```bash
   npm install -g pnpm
   ```

---

### **Step 4: Configure Environment Variables**

1. In the `frontend/` folder, create a file named `.env`

2. Copy this content into `.env`:

   ```env
   # Database connection
   DATABASE_URL=postgresql://ftias_user:ftias_password@localhost:5432/ftias_db

   # Backend API URL
   VITE_API_URL=http://localhost:8000

   # JWT Secret (use the same one from your backend)
   JWT_SECRET_KEY=your-secret-key-here-change-in-production
   ```

3. **Important:** Replace `your-secret-key-here-change-in-production` with the same JWT secret from your backend's `.env` file

---

### **Step 5: Start Your Backend**

1. Open a **new terminal** (keep this one open)

2. Navigate to your backend folder:

   ```bash
   cd flight-test-interactive-analysis-suite/backend
   ```

3. Make sure PostgreSQL is running (start it if needed)

   If you're using Docker (recommended on Windows):

   ```powershell
   # From the repo root (flight-test-interactive-analysis-suite/)
   docker compose up -d postgres
   docker compose ps
   ```

4. Start the backend:

   ```bash
   # If using virtual environment
   source venv/bin/activate  # On Windows: venv\Scripts\activate

   # Start the server
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. You should see:

   ```bash
   INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
   INFO:     Started reloader process
   ```

6. **Leave this terminal open** - the backend needs to keep running

---

### **Step 6: Start the Frontend**

1. Open **another new terminal** (you should now have 2 terminals open)

2. Navigate to the frontend folder:

   ```bash
   cd flight-test-interactive-analysis-suite/frontend
   ```

3. Start the frontend development server:

   ```bash
   pnpm dev
   ```

4. You should see:

   ```bash
   VITE v7.x.x  ready in xxx ms

   ➜  Local:   http://localhost:3000/
   ➜  Network: use --host to expose
   ```

5. **Leave this terminal open** - the frontend needs to keep running

---

### **Step 7: Open the Application**

1. Open your web browser

2. Go to: `http://localhost:3000`

3. You should see the Flight Test dashboard!

---

## ✅ Verification Checklist

Check that everything is working:

- [ ] Backend is running at `http://localhost:8000`
- [ ] Frontend is running at `http://localhost:3000`
- [ ] You can see the dashboard in your browser
- [ ] No error messages in either terminal

---

## 🐛 Troubleshooting

### **Problem: "Port 8000 already in use"**

**Solution:** Another program is using port 8000. Either:

- Stop the other program, OR
- Change the backend port:

  ```bash
  uvicorn app.main:app --reload --port 8001
  ```

  Then update `VITE_API_URL` in frontend `.env` to `http://localhost:8001`

### **Problem: "Port 3000 already in use"**

**Solution:** Change the frontend port:

```bash
pnpm dev --port 3001
```

### **Problem: "Database connection error"**

**Solution:**

1. Make sure PostgreSQL is running
2. Check that the database `ftias_db` exists
3. Verify the username and password in `.env` are correct

### **Problem: "pnpm: command not found"**

**Solution:** Install pnpm:

```bash
npm install -g pnpm
```

### **Problem: "Cannot find module" errors**

**Solution:** Delete `node_modules` and reinstall:

```bash
cd frontend
rm -rf node_modules
pnpm install
```

---

## 🎉 Success

If you see the dashboard at `http://localhost:3000`, congratulations! You've successfully set up the local development environment.

**Next:** Proceed to Part 2 (Frontend-Backend Integration) to connect the frontend to your existing backend API.

---

## 📝 Quick Reference

**To start everything:**

```bash
# Terminal 1: Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
pnpm dev
```

**To stop everything:**

- Press `CTRL+C` in each terminal

---

**Ready for Part 2?** Once you've verified everything is running, we'll connect the frontend to your backend API.
