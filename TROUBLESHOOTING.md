# MediaVault Troubleshooting Guide

This document contains common errors, diagnostics, and recovery procedures for MediaVault.

For each problem:

1. Identify the symptom or error.
2. Run the diagnostic command.
3. Check the expected result.
4. Apply the appropriate fix.
5. Restart MediaVault and test again.

---

# Table of Contents

1. [General Diagnostic Procedure](#1-general-diagnostic-procedure)
2. [Python Installation Errors](#2-python-installation-errors)
3. [Virtual Environment Errors](#3-virtual-environment-errors)
4. [Dependency Installation Errors](#4-dependency-installation-errors)
5. [Python Syntax Errors](#5-python-syntax-errors)
6. [FastAPI Startup Errors](#6-fastapi-startup-errors)
7. [Port 8000 Already in Use](#7-port-8000-already-in-use)
8. [Firefox Authentication Errors](#8-firefox-authentication-errors)
9. [gallery-dl Errors](#9-gallery-dl-errors)
10. [yt-dlp Errors](#10-yt-dlp-errors)
11. [No Posts Discovered](#11-no-posts-discovered)
12. [No Media Downloaded](#12-no-media-downloaded)
13. [Duplicate Posts](#13-duplicate-posts)
14. [Database Errors](#14-database-errors)
15. [Gallery Errors](#15-gallery-errors)
16. [Creator Synchronization Errors](#16-creator-synchronization-errors)
17. [Historical Import Errors](#17-historical-import-errors)
18. [Scheduler Errors](#18-scheduler-errors)
19. [Docker Errors](#19-docker-errors)
20. [Git Errors](#20-git-errors)
21. [Clean Reinstallation](#21-clean-reinstallation)
22. [Collecting Debug Information](#22-collecting-debug-information)

---

# 1. General Diagnostic Procedure

When MediaVault does not behave as expected, start with these checks.

## Step 1 — Confirm the project directory

```powershell
cd D:\Projects\HAHAHHAA\MediaVault
```

Check:

```powershell
Get-ChildItem
```

You should see directories/files similar to:

```text
app
database
gallery
README.md
TROUBLESHOOTING.md
requirements.txt
```

**Reference:** [Project Structure](README.md#5-project-structure)

---

## Step 2 — Activate the virtual environment

```powershell
.venv\Scripts\activate
```

The terminal should show:

```text
(.venv)
```

**Reference:** [Virtual Environment Errors](#3-virtual-environment-errors)

---

## Step 3 — Check Python

```powershell
python --version
```

Also check which Python executable is being used:

```powershell
where.exe python
```

The active executable should normally be inside:

```text
MediaVault\.venv\
```

**Reference:** [Python Installation Errors](#2-python-installation-errors)

---

## Step 4 — Check dependencies

```powershell
pip list
```

Check specifically:

```powershell
pip show fastapi
pip show uvicorn
pip show gallery-dl
pip show yt-dlp
```

**Reference:** [Dependency Installation Errors](#4-dependency-installation-errors)

---

## Step 5 — Check Python source files

```powershell
python -m py_compile app\main.py
python -m py_compile app\database.py
python -m py_compile app\downloader.py
python -m py_compile app\creator_downloader.py
python -m py_compile app\sync.py
python -m py_compile app\scheduler.py
```

If there is no output, compilation was successful.

**Reference:** [Python Syntax Errors](#5-python-syntax-errors)

---

# 2. Python Installation Errors

## Error

```text
'python' is not recognized as the name of a cmdlet
```

### Check

```powershell
python --version
```

### Fix

Install Python and ensure Python is added to PATH.

Restart PowerShell after installation.

Then run:

```powershell
python --version
```

---

## Error

```text
Python was not found
```

### Check

```powershell
where.exe python
```

### Fix

Install Python and recreate the virtual environment if necessary.

**Reference:** [Windows Installation](README.md#8-windows-installation)

---

# 3. Virtual Environment Errors

## Error

```text
.venv\Scripts\activate : The term ... is not recognized
```

### Check

```powershell
Test-Path .venv\Scripts\Activate.ps1
```

If it returns:

```text
False
```

the virtual environment does not exist.

### Fix

Create it again:

```powershell
python -m venv .venv
```

Then:

```powershell
.venv\Scripts\activate
```

---

## PowerShell Execution Policy Error

You may see an error similar to:

```text
running scripts is disabled on this system
```

### Fix

For the current PowerShell session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then:

```powershell
.venv\Scripts\activate
```

This change applies only to the current PowerShell session.

---

# 4. Dependency Installation Errors

## Error

```text
No module named 'fastapi'
```

or:

```text
No module named 'gallery_dl'
```

### Check

Make sure the virtual environment is active:

```powershell
python -c "import sys; print(sys.executable)"
```

The path should point to:

```text
MediaVault\.venv\
```

### Fix

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## Verify dependencies

```powershell
pip show fastapi
pip show uvicorn
pip show gallery-dl
pip show yt-dlp
```

---

# 5. Python Syntax Errors

## Error

Example:

```text
SyntaxError: invalid syntax
```

or:

```text
IndentationError
```

or:

```text
SyntaxError: f-string: expecting '}'
```

### Check

Run:

```powershell
python -m py_compile app\main.py
```

Python will identify the affected line.

Example:

```text
File "app\main.py", line 325
```

Go to that line and inspect the surrounding code.

### Common MediaVault Cause

`main.py` contains HTML/CSS/JavaScript inside Python f-strings.

Literal JavaScript/CSS braces must normally be doubled:

```python
{{

}}
```

instead of:

```python
{
}
```

### After fixing

Run:

```powershell
python -m py_compile app\main.py
```

No output means the syntax check passed.

---

# 6. FastAPI Startup Errors

## Error

```text
Error loading ASGI app
```

### Check

Run:

```powershell
python -m py_compile app\main.py
```

Then:

```powershell
python -c "from app.main import app; print(app)"
```

If the second command fails, inspect the traceback.

### Start MediaVault

```powershell
uvicorn app.main:app --reload
```

---

## Error

```text
ModuleNotFoundError
```

### Fix

Make sure the virtual environment is active:

```powershell
.venv\Scripts\activate
```

Then:

```powershell
pip install -r requirements.txt
```

---

# 7. Port 8000 Already in Use

## Error

```text
[Errno 10048]
```

or:

```text
address already in use
```

### Check

```powershell
netstat -ano | findstr :8000
```

You can also run MediaVault on another port.

### Fix

```powershell
uvicorn app.main:app --reload --port 8001
```

Open:

```text
http://127.0.0.1:8001
```

---

# 8. Firefox Authentication Errors

MediaVault v0.1.0 uses Firefox browser authentication.

The current workflow uses:

```text
gallery-dl --cookies-from-browser firefox
```

## Error

Posts are not discovered even though the creator exists.

### Step 1 — Open Firefox

Make sure Firefox is installed and available.

### Step 2 — Check login

Open the supported platform in Firefox and verify that you are logged in.

### Step 3 — Test gallery-dl directly

```powershell
gallery-dl --cookies-from-browser firefox <PROFILE_URL>/media
```

Replace:

```text
<PROFILE_URL>
```

with the creator's profile URL.

### If this command fails

The problem is likely related to gallery-dl, Firefox authentication, cookies, or the external platform rather than the MediaVault UI.

**Reference:** [gallery-dl Errors](#9-gallery-dl-errors)

---

## Firefox Profile Problems

If gallery-dl cannot find the Firefox profile, make sure Firefox has been run at least once and that the required profile exists.

Close Firefox and retry the gallery-dl command if necessary.

---

# 9. gallery-dl Errors

## Check installation

```powershell
gallery-dl --version
```

If this fails:

```powershell
pip install --upgrade gallery-dl
```

---

## Test a creator directly

```powershell
gallery-dl --cookies-from-browser firefox <PROFILE_URL>/media
```

This isolates MediaVault from gallery-dl.

---

## Error: authentication required

Verify:

1. Firefox is installed.
2. Firefox contains an active authenticated session.
3. The correct Firefox profile is being used.
4. The account can access the creator/profile manually.

---

## Error: no posts found

Possible causes include:

* Creator has no accessible posts.
* URL is incorrect.
* Authentication failed.
* External platform changed its website/API behavior.
* gallery-dl requires an update.

Update:

```powershell
pip install --upgrade gallery-dl
```

Then retry the direct gallery-dl command.

---

# 10. yt-dlp Errors

## Check version

```powershell
yt-dlp --version
```

Upgrade:

```powershell
pip install --upgrade yt-dlp
```

---

## Check installation

```powershell
python -c "import yt_dlp; print(yt_dlp.version.__version__)"
```

---

## Media download failure

Test the media URL directly using yt-dlp when appropriate:

```powershell
yt-dlp "<MEDIA_URL>"
```

If yt-dlp itself cannot process the URL, MediaVault may also be unable to download that media.

---

# 11. No Posts Discovered

If adding a creator succeeds but no posts appear:

### Step 1

Check the creator URL.

### Step 2

Verify Firefox authentication.

### Step 3

Test gallery-dl:

```powershell
gallery-dl --cookies-from-browser firefox <PROFILE_URL>/media
```

### Step 4

Check the MediaVault terminal output.

Look for messages such as:

```text
error
warning
timeout
authentication
```

### Step 5

Check gallery-dl version:

```powershell
gallery-dl --version
```

Update if necessary:

```powershell
pip install --upgrade gallery-dl
```

---

# 12. No Media Downloaded

If posts are discovered but media files are missing:

### Check the gallery directory

```powershell
Get-ChildItem gallery -Recurse
```

### Check the MediaVault terminal

Look for download errors.

### Check the post folder

The expected structure is:

```text
gallery/
└── creator/
    └── YYYY-MM-DD/
        └── post_ID/
            └── media
```

### Test the downloader separately

If a media URL is available:

```powershell
yt-dlp "<MEDIA_URL>"
```

**Reference:** [yt-dlp Errors](#10-yt-dlp-errors)

---

# 13. Duplicate Posts

MediaVault is designed to avoid downloading existing posts repeatedly.

If duplicates appear:

### Check database

The local database is:

```text
database/media.db
```

### Check the gallery

```powershell
Get-ChildItem gallery -Recurse
```

### Check MediaVault logs/terminal output

Look for whether the post was recognized as existing.

Do not manually delete database records unless you understand the effect.

---

# 14. Database Errors

## Database location

```text
database/media.db
```

## Check that the directory exists

```powershell
Test-Path database
```

Expected:

```text
True
```

---

## Check that the database exists

```powershell
Test-Path database\media.db
```

---

## Database initialization

MediaVault initializes the database during application startup.

Restart the application:

```powershell
uvicorn app.main:app --reload
```

---

## Database corruption

If the database is corrupted, make a backup before attempting recovery.

```powershell
Copy-Item database\media.db database\media_backup.db
```

Do not delete the original until the backup has been verified.

---

## Fresh database

For a completely fresh local database:

1. Stop MediaVault.
2. Back up the existing database.
3. Remove:

```text
database/media.db
```

4. Start MediaVault again.

The application should initialize a new database.

**WARNING:** This removes the application's knowledge of existing creators and posts. Downloaded media files may still exist in `gallery/`, but the database will no longer contain their records.

---

# 15. Gallery Errors

## Gallery is empty

Check:

```powershell
Get-ChildItem gallery -Recurse
```

If there are no downloaded files, check the download process.

---

## Gallery folder does not exist

Create it:

```powershell
New-Item -ItemType Directory -Force gallery
```

---

## Videos do not play

Check:

1. The video file exists.
2. The file extension is correct.
3. The browser supports the video format.
4. The downloaded file is not corrupted.

Test the file locally with another media player if necessary.

---

# 16. Creator Synchronization Errors

## Sync button fails

Check the MediaVault terminal for the error.

Then test the creator manually:

```powershell
gallery-dl --cookies-from-browser firefox <PROFILE_URL>/media
```

If gallery-dl fails, resolve the gallery-dl/authentication problem first.

---

## Existing posts are skipped

This is expected behavior.

MediaVault compares discovered posts with existing records and avoids downloading the same post again.

---

# 17. Historical Import Errors

Historical imports process posts in batches.

Current batch size:

```text
15 posts
```

If an import stops or fails:

### Step 1

Check the terminal output.

### Step 2

Check whether some posts were successfully imported.

### Step 3

Run the historical import again.

Existing posts should be skipped.

### Step 4

Check available disk space:

```powershell
Get-PSDrive
```

Large video archives can consume significant storage.

---

# 18. Scheduler Errors

The automatic scheduler currently runs every:

```text
15 minutes
```

If automatic synchronization does not occur:

### Check

Make sure MediaVault is still running.

The scheduler runs inside the MediaVault application process.

### Check terminal output

Look for:

```text
[Scheduler] Automatic sync started.
```

and:

```text
[Scheduler] Syncing:
```

If there are no enabled creators, the scheduler may report:

```text
[Scheduler] No enabled creators.
```

---

# 19. Docker Errors

## Check Docker

```powershell
docker --version
```

---

## Build MediaVault

```powershell
docker build -t mediavault:0.1.0 .
```

---

## Run MediaVault

```powershell
docker run --rm -p 8000:8000 mediavault:0.1.0
```

---

## Container exits immediately

Check:

```powershell
docker ps -a
```

Then:

```powershell
docker logs <CONTAINER_ID>
```

---

## Port conflict

Run on another host port:

```powershell
docker run --rm -p 8001:8000 mediavault:0.1.0
```

Then open:

```text
http://localhost:8001
```

---

## Important Docker authentication limitation

MediaVault v0.1.0 uses:

```text
gallery-dl --cookies-from-browser firefox
```

A normal Docker container does not automatically have access to the host's Firefox browser session.

Therefore, authenticated X downloading is currently intended for the Windows + Firefox configuration.

**Reference:** [Docker](README.md#27-docker)

---

# 20. Git Errors

## Check Git status

```powershell
git status
```

---

## Check remote

```powershell
git remote -v
```

Expected repository:

```text
https://github.com/JontySudha/MediaVault.git
```

---

## Check branch

```powershell
git branch
```

Expected:

```text
* main
```

---

## Push changes

```powershell
git add .
git commit -m "describe your change"
git push
```

---

## Check release tag

```powershell
git tag
```

Current release:

```text
v0.1.0
```

---

## Accidentally staged database/media

Check:

```powershell
git status
```

If local database or gallery files appear as staged files, do not commit.

Check `.gitignore`.

Remove the files from staging:

```powershell
git restore --staged database/media.db
```

For a gallery file:

```powershell
git restore --staged gallery/<path-to-file>
```

Then check:

```powershell
git status
```

---

# 21. Clean Reinstallation

If the installation is badly broken, perform a clean application environment setup.

## Step 1 — Stop MediaVault

Press:

```text
CTRL + C
```

in the terminal running Uvicorn.

---

## Step 2 — Remove the virtual environment

From the project directory:

```powershell
Remove-Item -Recurse -Force .venv
```

---

## Step 3 — Create a new environment

```powershell
python -m venv .venv
```

---

## Step 4 — Activate

```powershell
.venv\Scripts\activate
```

---

## Step 5 — Upgrade pip

```powershell
python -m pip install --upgrade pip
```

---

## Step 6 — Install dependencies

```powershell
pip install -r requirements.txt
```

---

## Step 7 — Verify Python files

```powershell
python -m py_compile app\main.py
python -m py_compile app\database.py
python -m py_compile app\downloader.py
python -m py_compile app\creator_downloader.py
python -m py_compile app\sync.py
python -m py_compile app\scheduler.py
```

---

## Step 8 — Start MediaVault

```powershell
uvicorn app.main:app --reload
```

---

# 22. Collecting Debug Information

When reporting a MediaVault problem, collect the following information.

## MediaVault version

```powershell
git describe --tags --always
```

---

## Git commit

```powershell
git log -1 --oneline
```

---

## Python version

```powershell
python --version
```

---

## gallery-dl version

```powershell
gallery-dl --version
```

---

## yt-dlp version

```powershell
yt-dlp --version
```

---

## FastAPI version

```powershell
pip show fastapi
```

---

## Uvicorn version

```powershell
pip show uvicorn
```

---

## Operating system

```powershell
Get-ComputerInfo | Select-Object WindowsProductName, WindowsVersion, OsArchitecture
```

---

## Git status

```powershell
git status
```

---

## Important

Do **not** include passwords, authentication cookies, browser session files, API tokens, private keys, or other credentials when sharing diagnostic information.

---

# 23. Quick Diagnostic Checklist

Use this checklist when MediaVault is not working.

```text
[ ] Project directory is correct
[ ] Python is installed
[ ] Virtual environment is active
[ ] Dependencies are installed
[ ] main.py compiles successfully
[ ] Database directory exists
[ ] Gallery directory exists
[ ] Firefox is installed
[ ] Firefox is authenticated
[ ] gallery-dl works independently
[ ] yt-dlp is installed
[ ] Port 8000 is available
[ ] MediaVault starts successfully
[ ] Creator URL is correct
[ ] Disk space is available
```

---

# 24. Recommended Diagnostic Order

When troubleshooting, use this order:

```text
Python
   ↓
Virtual Environment
   ↓
Dependencies
   ↓
Python Syntax
   ↓
FastAPI
   ↓
Firefox Authentication
   ↓
gallery-dl
   ↓
Media Discovery
   ↓
Media Download
   ↓
SQLite Database
   ↓
Gallery
   ↓
Scheduler
   ↓
Docker
```

This order helps isolate the failure before changing multiple components at once.

---

# 25. Before Reporting a Bug

Please collect:

```powershell
python --version
gallery-dl --version
yt-dlp --version
git describe --tags --always
git status
```

Also include:

* The exact error message
* The command that produced the error
* The MediaVault page/action that triggered it
* Whether Firefox authentication works
* Whether the same URL works directly with gallery-dl
* Whether the problem affects one creator or all creators

Never include passwords, cookies, authentication tokens, or private credentials.
