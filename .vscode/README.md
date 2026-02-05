# VSCode Configuration for FTIAS

This directory contains VSCode workspace configuration files that provide an optimized development environment for the FTIAS project.

## Files Overview

### `settings.json`

Workspace settings that configure:

- **Python**: Black formatter, Flake8 linter, pytest integration
- **TypeScript/React**: Prettier formatter, ESLint linter
- **Editor**: Format on save, rulers at 100/120 characters
- **File exclusions**: Hide `__pycache__`, `node_modules`, etc.

### `extensions.json`

Recommended extensions for the project. VSCode will prompt you to install these when you open the workspace.

**Essential Extensions:**

- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- ESLint (dbaeumer.vscode-eslint)
- Prettier (esbenp.prettier-vscode)
- Docker (ms-azuretools.vscode-docker)
- GitLens (eamodio.gitlens)

### `launch.json`

Debug configurations for:

- **Python: FastAPI** - Debug the backend server
- **Python: pytest** - Debug tests
- **Chrome: Frontend** - Debug React app in Chrome
- **Full Stack** - Debug both frontend and backend simultaneously

### `tasks.json`

Pre-configured tasks for common operations:

- Docker commands (start, stop, rebuild)
- Backend tasks (test, lint, format)
- Frontend tasks (dev server, build, test)
- Database tasks (connect, backup)

## Getting Started

### 1. Install Recommended Extensions

When you open this workspace in VSCode, you'll see a notification to install recommended extensions. Click **Install All** to get started quickly.

Alternatively, you can install them manually:

1. Press `Ctrl+Shift+X` (Windows) or `Cmd+Shift+X` (Mac)
2. Search for each extension in `extensions.json`
3. Click Install

### 2. Configure Python Interpreter

1. Press `Ctrl+Shift+P` (Windows) or `Cmd+Shift+P` (Mac)
2. Type "Python: Select Interpreter"
3. Choose the interpreter from `.venv` folder:
   - Windows: `.venv\Scripts\python.exe`
   - Mac/Linux: `.venv/bin/python`

### 3. Verify Configuration

Open the Command Palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) and run:

- **Python: Run Linting** - Should use Flake8
- **Format Document** - Should use Black for Python, Prettier for TypeScript

## Using Debug Configurations

### Debug Backend

1. Set breakpoints in your Python code
2. Press `F5` or go to Run and Debug panel
3. Select **"Python: FastAPI"** configuration
4. The backend will start with debugger attached

### Debug Frontend

1. Start the frontend dev server (or use Docker)
2. Set breakpoints in your TypeScript/React code
3. Press `F5` and select **"Chrome: Frontend"**
4. Chrome will open with debugging enabled

### Debug Full Stack

1. Press `F5` and select **"Full Stack"**
2. Both backend and frontend will start with debugging enabled
3. Set breakpoints in either codebase

## Using Tasks

### Run a Task

1. Press `Ctrl+Shift+P` (Windows) or `Cmd+Shift+P` (Mac)
2. Type "Tasks: Run Task"
3. Select the task you want to run

### Common Tasks

**Docker:**

- `Docker: Start All Services` - Start all containers
- `Docker: Stop All Services` - Stop all containers
- `Docker: View Logs` - View container logs

**Backend:**

- `Backend: Run Tests` - Run pytest
- `Backend: Format Code (Black)` - Format Python code
- `Backend: Lint (Flake8)` - Lint Python code

**Frontend:**

- `Frontend: Dev Server` - Start Vite dev server
- `Frontend: Run Tests` - Run Jest tests
- `Frontend: Lint` - Run ESLint

**Compound Tasks:**

- `Setup: Install All Dependencies` - Install backend and frontend deps
- `Test: Run All Tests` - Run all tests
- `Format: Format All Code` - Format all code

### Configure Default Build Task

1. Press `Ctrl+Shift+B` (Windows) or `Cmd+Shift+B` (Mac)
2. Select "Configure Default Build Task"
3. Choose your preferred task (e.g., "Docker: Start All Services")

Now `Ctrl+Shift+B` will run that task directly.

## Keyboard Shortcuts

### Default VSCode Shortcuts

- `F5` - Start Debugging
- `Ctrl+Shift+B` - Run Build Task
- `Ctrl+Shift+P` - Command Palette
- `Ctrl+`` - Toggle Terminal
- `Ctrl+Shift+F` - Search in Files
- `Ctrl+P` - Quick Open File

### Custom Shortcuts (Optional)

You can add custom shortcuts in **File > Preferences > Keyboard Shortcuts**:

```json
[
  {
    "key": "ctrl+shift+t",
    "command": "workbench.action.tasks.runTask",
    "args": "Backend: Run Tests"
  },
  {
    "key": "ctrl+shift+d",
    "command": "workbench.action.tasks.runTask",
    "args": "Docker: Start All Services"
  }
]
```

## Linting and Formatting

### Python (Backend)

**Linter:** Flake8

- Runs automatically on save
- Max line length: 100 characters
- Ignores: E203, W503 (for Black compatibility)

**Formatter:** Black

- Runs automatically on save
- Line length: 100 characters

**Import Sorter:** isort

- Runs automatically on save
- Profile: black (for compatibility)

### TypeScript/React (Frontend)

**Linter:** ESLint

- Runs automatically on save
- Configuration: `.eslintrc.json` in frontend folder

**Formatter:** Prettier

- Runs automatically on save
- Single quotes, trailing commas, 100 char line length

## Troubleshooting

### Extensions Not Working

1. Reload VSCode: `Ctrl+Shift+P` → "Developer: Reload Window"
2. Check extension status: `Ctrl+Shift+X`
3. Verify Python interpreter is selected

### Linter Not Running

1. Check Output panel: `View > Output`
2. Select "Python" or "ESLint" from dropdown
3. Look for error messages

### Formatter Not Working

1. Right-click in editor → "Format Document With..."
2. Select the correct formatter (Black for Python, Prettier for TS)
3. Set as default if prompted

### Python Import Errors

1. Ensure virtual environment is activated
2. Check `PYTHONPATH` in terminal: `echo $env:PYTHONPATH` (PowerShell)
3. Verify `settings.json` has correct Python path

### Tasks Not Found

1. Reload window: `Ctrl+Shift+P` → "Developer: Reload Window"
2. Check `tasks.json` for syntax errors
3. Ensure you're in the workspace root

## Tips and Best Practices

### Multi-root Workspace (Optional)

For better organization, you can create a multi-root workspace:

1. **File > Add Folder to Workspace**
2. Add `backend` and `frontend` as separate roots
3. **File > Save Workspace As...**

This allows separate settings for each folder.

### Integrated Terminal

Use the integrated terminal for running commands:

- `` Ctrl+` `` to toggle terminal
- Multiple terminals: Click `+` in terminal panel
- Split terminal: Click split icon

### Source Control

GitLens extension provides powerful Git features:

- Inline blame annotations
- File history
- Compare branches
- And much more

### Code Snippets

Install snippet extensions for faster coding:

- Python snippets
- React snippets (ES7+ React/Redux/React-Native)

### Remote Development (Optional)

If using WSL2 or remote servers:

1. Install "Remote - WSL" or "Remote - SSH" extension
2. Connect to remote environment
3. All settings and extensions sync automatically

## Additional Resources

- [VSCode Python Tutorial](https://code.visualstudio.com/docs/python/python-tutorial)
- [VSCode TypeScript Tutorial](https://code.visualstudio.com/docs/typescript/typescript-tutorial)
- [Debugging in VSCode](https://code.visualstudio.com/docs/editor/debugging)
- [Tasks in VSCode](https://code.visualstudio.com/docs/editor/tasks)

## Support

If you encounter issues with VSCode configuration:

1. Check this README
2. Review VSCode documentation
3. Open an issue on GitHub with the `vscode` label
