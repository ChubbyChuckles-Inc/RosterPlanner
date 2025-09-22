# Project Template

[![CI](https://github.com/ChubbyChuckles/project-template/actions/workflows/ci.yml/badge.svg)](https://github.com/ChubbyChuckles/project-template/actions/workflows/ci.yml)
[![Docs](https://readthedocs.org/projects/project-template/badge/?version=latest)](https://project-template.readthedocs.io)

This is a Python project template with automated setup for creating new projects, including a virtual environment, dependency installation, Sphinx documentation, and Git workflow with pre-commit checks.

## Setup Instructions

This template automates the setup of a new Python project. Follow these steps to initialize a new project after cloning or using this template.

### Prerequisites (Outside VS Code)

Before starting, ensure the following are set up on your Windows 10 system:

1. **Install Git**:

   - Download and install Git for Windows from [https://git-scm.com/](https://git-scm.com/).
   - Verify installation by running in Command Prompt or PowerShell:
     ```powershell
     git --version
     ```
   - Ensure Git is added to your system PATH (selected during installation).

2. **Install Python**:

   - Ensure Python 3.12.3 or later is installed. Download from [https://www.python.org/](https://www.python.org/).
   - Verify installation:
     ```powershell
     python --version
     ```
   - Ensure `pip` is available:
     ```powershell
     python -m pip --version
     ```

3. **Set PowerShell Execution Policy**:

   - To run PowerShell scripts like `scripts/commit-push.ps1`, set the execution policy to allow scripts:
     ```powershell
     Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
     ```
   - Run this in an elevated PowerShell prompt (right-click PowerShell and select "Run as administrator").
   - If prompted, type `Y` to confirm.

4. **Install Visual Studio Code (Optional but Recommended)**:
   - Download and install VS Code from [https://code.visualstudio.com/](https://code.visualstudio.com/).
   - Install the Python extension for VS Code (by Microsoft) for better Python support:
     - Open VS Code, go to the Extensions view (`Ctrl+Shift+X`), search for "Python," and install the Microsoft Python extension.

### Setup Steps

1. **Clone the Repository or Create a New Project**:

   - Clone this repository:
     ```powershell
     git clone https://github.com/ChubbyChuckles/project-template.git <new-project-name>
     cd <new-project-name>
     ```
   - Alternatively, use the "Use this template" button on GitHub to create a new repository, then clone it:
     ```powershell
     git clone https://github.com/<your-username>/<your-new-repo>.git
     cd <your-new-repo>
     ```

2. **Run the Bootstrap Script**:

   - Run the `bootstrap.py` script to automate setup:
     ```powershell
     python bootstrap.py
     ```
   - Follow the prompts:
     - **Enter the new project name** (e.g., `MyNewProject`).
     - **Enter the new GitHub repository URL** (e.g., `https://github.com/ChubbyChuckles/my-new-project.git`).
   - The script will:
     - Create a virtual environment (`.venv`).
     - Install dependencies from `requirements.txt` (e.g., `numpy`, `pandas`, `matplotlib`, `sphinx`, `pre-commit`).
     - Create a `.env` file in the root directory with the project name and placeholder environment variables.
     - Update `README.md`, `setup.py`, and `docs/source/conf.py` with the new project name and author.
     - Initialize a Git repository (if needed) and set the new remote URL.
     - Create and switch to a `develop` branch.
     - Run `scripts/commit-push.ps1` to stage, commit, and push changes to the `develop` branch.

3. **Inside VS Code**:
   - **Open the Project**:
     - Launch VS Code and open the project folder:
       ```powershell
       code .
       ```
     - Alternatively, open VS Code, go to `File > Open Folder`, and select the project directory (e.g., `C:\Users\Chuck\Desktop\CR_AI_Engineering\Projekte\Github_Repo_Template\<new-project-name>`).
   - **Select Python Interpreter**:
     - Press `Ctrl+Shift+P` to open the Command Palette.
     - Type `Python: Select Interpreter` and select the virtual environment (`.venv\Scripts\python.exe`).
   - **Run `bootstrap.py` in VS Code** (if not run earlier):
     - Open `bootstrap.py` in VS Code.
     - Right-click the file and select `Run Python File in Terminal`, or use the integrated terminal:
       ```powershell
       python bootstrap.py
       ```
   - **Edit Configuration Files**:
     - Update `docs/source/conf.py` for additional Sphinx settings (e.g., add custom modules for `autodoc`).
     - Modify `README.md` or `setup.py` to add project-specific details.
     - Use VS Code’s built-in Git integration (Source Control tab) to stage, commit, and push changes:
       - Click the Source Control icon in the sidebar.
       - Stage changes by clicking the `+` next to modified files.
       - Enter a commit message and click the checkmark to commit.
       - Click the `...` menu and select `Push` to push to the remote repository.
   - **Generate Sphinx Documentation**:
     - Open the integrated terminal in VS Code (`Ctrl+``).
     - Run:
       ```powershell
       cd docs
       .\make.bat html
       ```
     - Open `docs/build/html/index.html` in a browser to verify the documentation.

### Troubleshooting

### Running a Full Scrape (CLI & GUI)

You can populate the application dataset by running the scrape pipeline either via CLI or directly inside the GUI:

CLI:

```powershell
python -m src.main run-full --club 2294 --season 2025 --out data
```

GUI:

1. Launch the GUI:

```powershell
python -m gui.app
```

2. Use the menu: `Data > Run Full Scrape`.
3. Wait for the status bar to show completion; the navigation tree will refresh automatically.

If a scrape is already running the action is disabled (or you will be notified). Errors appear in a dialog.

### Automatic Ingestion of Existing Scrape Assets (Auto-Ingest Fallback)

If you previously ran a scrape (via CLI, another machine, or an earlier session) and the HTML assets already exist under the configured `data` directory, the GUI now attempts to make those teams immediately available without requiring a manual ingestion step.

Behavior overview:

1. On startup (initial landing load) the application checks the database state. If there are no ingested teams/provenance rows yet (empty DB gate) it performs a lightweight scan of `DATA_DIR`.
2. If at least one `ranking_table_*.html` or `team_roster_*.html` file is found, an automatic ingestion pass is triggered (filename audit → derived divisions/teams → DB insert + provenance rows).
3. After ingestion succeeds the navigation tree is populated with the available teams. If ingestion fails, the failure is logged to stderr and the UI simply shows an empty state (allowing you to still run a fresh full scrape).

Key points / limitations:

- The auto-ingest only runs when the DB is empty (no previously ingested data). It will not overwrite or re-import existing records.
- It is heuristic: presence of at least one qualifying HTML file triggers it. Partial or malformed sets may lead to fewer teams than expected; running a full scrape will reconcile.
- Failures are intentionally non-blocking; they do not present a modal error dialog—look at stderr / logs for `[LandingLoadWorker] Auto-ingest failed:` messages.
- Provenance rows are created during this process so subsequent launches skip the fallback and load directly from the DB.

Future enhancements (tracked/planned):

- Preference/flag to disable auto-ingest for power users who want a clean manual ingest.
- Progress / toast notification in the GUI when auto-ingest runs.
- Retry button in the empty state panel if assets are detected but initial ingest failed.

Manual override: If you want to force a fresh end‑to‑end scrape even after auto-ingest, just use `Data > Run Full Scrape`; existing DB entries will be augmented/updated according to the scrape + ingestion rules.

### Division Persistence & GUI Fallback (New)

After a successful full scrape the application now serializes the complete division → teams mapping into `data/match_tracking.json`. If the SQLite ingestion has not yet been performed (or the DB was cleared) but that JSON exists, the GUI landing tree will populate divisions/teams directly from the tracking file. This prevents an empty navigation tree immediately after a scrape and before (or in lieu of) ingestion.

Implications:

- Running a scrape alone gives you a browsable division/team tree on next launch (even without DB ingest).
- Once ingestion runs, the DB remains the primary source and the fallback is bypassed.
- If you delete the DB but keep `match_tracking.json`, the tree still appears (until a new ingest occurs).

To disable this behavior temporarily, remove or rename `match_tracking.json` before launching the GUI.

- **Pre-Commit Hook Failures**:

  - If `scripts/commit-push.ps1` fails due to pre-commit hooks (e.g., `black`, `flake8`, `sphinx-build`), check the error output in the terminal.
  - Ensure all dependencies are installed:
    ```powershell
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    ```
  - Verify Sphinx files (`docs/Makefile`, `docs/make.bat`, `docs/source/conf.py`, `docs/source/index.rst`) exist.
  - If issues persist, open `.pre-commit-config.yaml` in VS Code and check the `sphinx-build` hook configuration:
    ```yaml
    - repo: local
      hooks:
        - id: sphinx-build
          name: Build Sphinx documentation
          entry: make html
          language: system
          files: ^docs/
    ```

- **Git Push Errors**:

  - If `git push` fails, verify the GitHub URL and ensure you have push access.
  - Use a personal access token if authentication fails:
    ```powershell
    git remote set-url origin https://<username>:<token>@github.com/<username>/<repo>.git
    ```
    Generate a token in GitHub: `Settings > Developer settings > Personal access tokens > Tokens (classic)`.

- **Dependency Issues**:

  - If `pip install -r requirements.txt` fails, check for conflicting versions in `requirements.txt`.
  - Run in the VS Code terminal:
    ```powershell
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    ```

- **Virtual Environment Issues**:

  - Ensure `.venv` is not ignored in `.gitignore`.
  - If the virtual environment fails to activate, recreate it:
    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    ```

- **.env File Issues**:
  - The `bootstrap.py` script creates a `.env` file with the project name and example variables.
  - Edit `.env` in VS Code to add project-specific environment variables (e.g., API keys, database URLs).
  - Do not commit sensitive data to `.env`. For production use, add `.env` to `.gitignore` after setup and use a `.env.example` file for templates.

### Documentation

- Documentation is built with Sphinx. To generate HTML documentation:
  ```powershell
  cd docs
  .\make.bat html
  ```

## Repository Structure

- `bootstrap.py`: Automates project setup.
- `requirements.txt`: Lists dependencies (e.g., `numpy`, `pandas`, `sphinx`, `pre-commit`).
- `scripts/commit-push.ps1`: PowerShell script for staging, committing, and pushing changes.
- `docs/`: Contains Sphinx files (`Makefile`, `make.bat`, `source/conf.py`, `source/index.rst`).
- `.pre-commit-config.yaml`: Configures pre-commit hooks.
- `setup.py`: Python package configuration.
- `.env`: Template file for environment variables.
- `README.md`: This file.

For further customization, edit `setup.py`, `docs/source/conf.py`, `.env`, or add Python modules to the repository.

## Roadmap (Implemented Milestones Extract)

The following internal milestones have been implemented to evolve the GUI/service infrastructure:

- 1.2 / 1.2.1: Single-instance guard and bootstrap enhancements
- 1.2.2: Startup timing logger with JSON export
- 1.3 / 1.3.1: Config-driven startup and window geometry version invalidation
- 1.4 / 1.4.1: Service locator enhancements and repository injection helpers
- 1.5: Typed `EventBus` signals (core synchronous pub/sub)
- 1.5.1: Event tracing (recent event ring buffer)
- 1.5.2: Auto-ingest fallback for pre-existing scrape assets (startup HTML → DB bridging)

### Milestone 1.5.1 – EventBus Tracing

Adds lightweight, toggleable tracing for recently published GUI events to aid diagnostics and future debug overlays.

Key points:

- Disabled by default; enable via:
  ```python
  from gui.services import event_tracing
  event_tracing.enable_event_tracing(capacity=100)  # optional custom capacity
  ```
- Captures a fixed-size ring buffer (default 50) of `TraceEntry` objects: `(name, timestamp, summary)`.
- Summaries are a short string form of the payload (truncated to 40 chars, or '-' if None).
- Access recent traces:
  ```python
  traces = event_tracing.get_recent_event_traces()
  for t in traces:
      print(t.timestamp, t.name, t.summary)
  ```
- Disable tracing to freeze the current buffer:
  ```python
  event_tracing.disable_event_tracing()
  ```

Test Coverage:

- Basic capture and ordering
- Ring buffer capacity / eviction behavior
- Disable stops further capture while retaining existing entries
- No-op behavior when disabled

This foundation will support forthcoming debugging UIs (e.g., an in-app overlay listing the last N events).
