# MediaVault

**MediaVault** is a local-first creator media archiving and synchronization platform built with Python, FastAPI, SQLite, gallery-dl, and yt-dlp.

It allows users to track creator profiles, discover posts, download available media, store post metadata, organize downloaded content locally, and automatically synchronize new posts.

---

## Features

* Creator profile management
* Post discovery
* Image, video, GIF, and audio downloading
* Post description/caption storage
* Post metadata storage
* Local SQLite database
* Creator-specific galleries
* Centralized post view
* Direct video playback
* New-post synchronization
* Historical post importing
* Automatic background synchronization
* Duplicate-post detection
* Post deletion
* Creator deletion
* Creator mention detection
* Docker support for application testing

---

# 1. Architecture

```text
                         ┌──────────────────┐
                         │      Browser     │
                         │   MediaVault UI  │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │     FastAPI      │
                         │   Web Backend    │
                         └────────┬─────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
             ┌───────────┐ ┌────────────┐ ┌────────────┐
             │  SQLite   │ │ gallery-dl │ │   yt-dlp   │
             │ Database  │ │ Discovery  │ │ Downloader  │
             └───────────┘ └────────────┘ └────────────┘
                    │             │             │
                    └─────────────┼─────────────┘
                                  ▼
                         ┌──────────────────┐
                         │  Local Gallery   │
                         │ Downloaded Media │
                         └──────────────────┘
```

---

# 2. Technology Stack

| Component        | Technology              |
| ---------------- | ----------------------- |
| Language         | Python                  |
| Backend          | FastAPI                 |
| ASGI Server      | Uvicorn                 |
| Database         | SQLite                  |
| Post Discovery   | gallery-dl              |
| Media Download   | gallery-dl / yt-dlp     |
| Frontend         | HTML / CSS / JavaScript |
| Containerization | Docker                  |
| Version Control  | Git / GitHub            |
| Primary OS       | Windows                 |
| Authentication   | Firefox browser session |

---

# 3. Project Structure

```text
MediaVault/
│
├── app/
│   ├── __init__.py
│   ├── database.py
│   ├── downloader.py
│   ├── creator_downloader.py
│   ├── main.py
│   ├── scheduler.py
│   └── sync.py
│
├── database/
│   └── .gitkeep
│
├── gallery/
│   └── .gitkeep
│
├── .gitignore
├── .dockerignore
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── README.md
├── TROUBLESHOOTING.md
└── LICENSE
```

Downloaded media and the SQLite database are intentionally excluded from Git.

---

# 4. Requirements

For the current Windows release you need:

* Windows 10 or Windows 11
* Python 3.11 or newer
* Firefox
* Git
* Internet connection

Optional:

* Docker Desktop

> **Troubleshooting:** If Python is not recognized, see [Python Installation Errors](TROUBLESHOOTING.md#2-python-installation-errors).

---

# 5. Installation

## Step 1 — Install Python

Verify Python:

```powershell
python --version
```

Also check:

```powershell
where.exe python
```

You should have a supported Python installation.

> **Troubleshooting:** See [Python Installation Errors](TROUBLESHOOTING.md#2-python-installation-errors).

---

## Step 2 — Clone MediaVault

```powershell
git clone https://github.com/JontySudha/MediaVault.git
cd MediaVault
```

> **Troubleshooting:** See [Git Errors](TROUBLESHOOTING.md#20-git-errors).

---

## Step 3 — Create the Virtual Environment

```powershell
python -m venv .venv
```

Activate it:

```powershell
.venv\Scripts\activate
```

Your terminal should show:

```text
(.venv)
```

> **Troubleshooting:** See [Virtual Environment Errors](TROUBLESHOOTING.md#3-virtual-environment-errors).

---

## Step 4 — Upgrade pip

```powershell
python -m pip install --upgrade pip
```

> **Troubleshooting:** See [Dependency Installation Errors](TROUBLESHOOTING.md#4-dependency-installation-errors).

---

## Step 5 — Install Dependencies

```powershell
pip install -r requirements.txt
```

Verify:

```powershell
pip show fastapi
pip show uvicorn
pip show gallery-dl
pip show yt-dlp
```

> **Troubleshooting:** See [Dependency Installation Errors](TROUBLESHOOTING.md#4-dependency-installation-errors).

---

# 6. Verify the Installation

Before starting MediaVault, compile the Python modules:

```powershell
python -m py_compile app\main.py
python -m py_compile app\database.py
python -m py_compile app\downloader.py
python -m py_compile app\creator_downloader.py
python -m py_compile app\sync.py
python -m py_compile app\scheduler.py
```

No output means the syntax checks passed.

> **Troubleshooting:** See [Python Syntax Errors](TROUBLESHOOTING.md#5-python-syntax-errors).

---

# 7. Firefox Authentication

MediaVault v0.1.0 uses the authenticated Firefox browser session.

The current workflow uses:

```text
gallery-dl --cookies-from-browser firefox
```

### Setup

1. Install Firefox.
2. Open Firefox.
3. Log into the supported platform.
4. Keep the authenticated Firefox profile available.
5. Start MediaVault.

MediaVault does not require you to enter your platform password into the application.

> **Troubleshooting:** See [Firefox Authentication Errors](TROUBLESHOOTING.md#8-firefox-authentication-errors).

---

# 8. Start MediaVault

Development mode:

```powershell
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

Production-style local run:

```powershell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

> **Troubleshooting:** See [FastAPI Startup Errors](TROUBLESHOOTING.md#6-fastapi-startup-errors).

---

# 9. Add a Creator

Open:

```text
http://127.0.0.1:8000
```

Enter the creator profile URL.

MediaVault will:

1. Normalize the URL.
2. Identify the creator.
3. Add the creator to SQLite.
4. Attempt to discover available posts.
5. Display the creator in the application.

> **Troubleshooting:** If no posts are discovered, see [No Posts Discovered](TROUBLESHOOTING.md#11-no-posts-discovered).

---

# 10. Sync New Posts

Use:

**Sync New Posts**

MediaVault will:

1. Discover currently available posts.
2. Compare them with existing database records.
3. Skip posts already stored.
4. Download newly discovered media.
5. Save metadata.
6. Store media information in SQLite.
7. Organize files in the gallery.

> **Troubleshooting:** See [Creator Synchronization Errors](TROUBLESHOOTING.md#16-creator-synchronization-errors).

---

# 11. Import Older Posts

Use:

**Import Older Posts**

This is intended for historical content.

Historical imports are processed in batches of:

```text
15 posts
```

Existing posts are skipped.

This allows a large archive to be built progressively.

> **Troubleshooting:** See [Historical Import Errors](TROUBLESHOOTING.md#17-historical-import-errors).

---

# 12. Gallery

Downloaded media is organized using:

```text
gallery/
└── <creator_name>/
    └── <YYYY-MM-DD>/
        └── post_<post_id>/
            ├── media files
            └── metadata
```

Example:

```text
gallery/
└── CreatorName/
    └── 2026-09-20/
        └── post_123456789/
            ├── video.mp4
            └── metadata.json
```

The creator gallery allows locally downloaded images, videos, and audio to be viewed from MediaVault.

> **Troubleshooting:** See [Gallery Errors](TROUBLESHOOTING.md#15-gallery-errors).

---

# 13. Home Page

The main page provides access to:

* Tracked creators
* Creator management
* Post browsing
* Synchronization
* Historical imports

Posts are displayed across creators and sorted by post date.

---

# 14. Creator Page

Each tracked creator has an individual page containing:

* Creator information
* Posts
* Descriptions
* Downloaded media
* Gallery access
* New-post synchronization
* Historical import
* Delete controls

---

# 15. Creator Mentions

MediaVault detects supported creator mentions in post descriptions.

For example:

```text
@username
```

Tracked creators can be linked to their local creator page while retaining a link to the external profile.

---

# 16. Delete a Post

MediaVault allows individual posts to be deleted.

Deleting a post removes:

* Its local post directory
* Its database record

Use this carefully because locally downloaded media is removed.

---

# 17. Delete a Creator

Deleting a creator removes:

* The creator database record
* The creator's local gallery directory
* Associated locally archived content

Use this operation carefully.

---

# 18. Automatic Synchronization

MediaVault contains a background scheduler.

Current interval:

```text
15 minutes
```

The scheduler:

1. Loads enabled creators.
2. Synchronizes each creator.
3. Downloads newly discovered content.
4. Waits for the next interval.

The scheduler only runs while MediaVault itself is running.

> **Troubleshooting:** See [Scheduler Errors](TROUBLESHOOTING.md#18-scheduler-errors).

---

# 19. Database

MediaVault uses SQLite.

Default database:

```text
database/media.db
```

The database stores information such as:

* Creators
* Posts
* Media
* Post dates
* Download timestamps
* Creator relationships
* Metadata

The database is intentionally excluded from Git.

> **Troubleshooting:** See [Database Errors](TROUBLESHOOTING.md#14-database-errors).

---

# 20. Docker

Docker support is included for application/container testing.

Build:

```powershell
docker build -t mediavault:0.1.0 .
```

Run:

```powershell
docker run --rm -p 8000:8000 mediavault:0.1.0
```

Open:

```text
http://localhost:8000
```

> **Important:** Docker does not currently provide browser-independent authenticated X downloading.

> **Troubleshooting:** See [Docker Errors](TROUBLESHOOTING.md#19-docker-errors).

---

# 21. Docker Compose

Start:

```powershell
docker compose up --build
```

Stop:

```powershell
docker compose down
```

The Compose configuration mounts:

```text
./database
./gallery
```

into the container.

---

# 22. Docker Authentication Limitation

v0.1.0 currently relies on:

```text
gallery-dl --cookies-from-browser firefox
```

A normal Docker container does not automatically have access to the host machine's Firefox browser session.

Therefore the primary supported configuration for v0.1.0 is:

```text
Windows
   +
Firefox
   +
MediaVault
```

Browser-independent authentication is planned for a future release.

---

# 23. Security

Do not commit:

* Browser cookies
* Authentication files
* Passwords
* API tokens
* Private keys
* Session files
* Local databases
* Downloaded media

The repository `.gitignore` is configured to exclude common sensitive/local files.

---

# 24. Privacy

MediaVault is designed as a local-first application.

Downloaded media and application metadata are stored locally.

The application does not require a MediaVault cloud account for basic operation.

Users are responsible for complying with:

* Platform terms
* Copyright requirements
* Creator rights
* Applicable laws

---

# 25. Troubleshooting

The dedicated troubleshooting guide contains diagnostic commands and recovery procedures.

**Troubleshooting Guide:**

[TROUBLESHOOTING.md](TROUBLESHOOTING.md)

Common categories include:

* Python
* Virtual environment
* Dependencies
* Syntax errors
* FastAPI
* Firefox authentication
* gallery-dl
* yt-dlp
* Downloads
* SQLite
* Gallery
* Scheduler
* Docker
* Git

---

# 26. Development

Check repository status:

```powershell
git status
```

Run syntax checks:

```powershell
python -m py_compile app\main.py
```

Start development server:

```powershell
uvicorn app.main:app --reload
```

---

# 27. Git Release

Current release:

```text
v0.1.0
```

Check tags:

```powershell
git tag
```

Check current commit:

```powershell
git log --oneline --decorate -5
```

---

# 28. Roadmap

## v0.1.x

* UI improvements
* Improved error handling
* Better metadata extraction
* Download recovery
* Additional testing

## v0.2.0

Planned:

* Browser-independent authentication
* Improved session management
* Better container compatibility
* Improved downloader architecture

## Future

Potential features:

* Multiple platform support
* Search
* Filtering
* Tags
* Download queues
* Progress tracking
* API
* Monitoring
* Backup/restore
* Docker-first deployment
* Cloud deployment

---

# 29. Multi-Platform Architecture

MediaVault is intended to eventually support multiple platforms.

The long-term architecture is:

```text
                         MediaVault
                             │
                     Platform Interface
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
          Platform A    Platform B    Platform C
              │              │              │
              └──────────────┼──────────────┘
                             ▼
                       Media Pipeline
                             │
                    ┌────────┴────────┐
                    ▼                 ▼
                 SQLite            Gallery
```

This keeps platform-specific discovery separate from the core application.

---

# 30. Backup

The most important local directories are:

```text
database/
gallery/
```

Back up both directories to protect the application metadata and downloaded media.

---

# 31. Performance

Storage requirements depend on:

* Number of creators
* Number of posts
* Video resolution
* Video duration
* Number of images
* Number of downloaded media files

Historical imports are processed in batches to reduce resource usage.

---

# 32. Responsible Use

MediaVault is intended for legitimate personal archiving, research, backup, and content-management purposes.

Users are responsible for:

* Respecting copyright
* Respecting platform terms
* Respecting creator rights
* Following applicable laws
* Protecting downloaded content
* Protecting authentication sessions

Do not use MediaVault to bypass access controls or obtain content you are not authorized to access.

---

# 33. License

See the `LICENSE` file included in this repository.

---

# 34. Version History

## v0.1.0 — Firefox Edition

Initial release containing:

* FastAPI application
* SQLite database
* Creator management
* Post discovery
* Media downloading
* Local gallery
* Creator galleries
* Historical imports
* New-post synchronization
* Automatic scheduler
* Post deletion
* Creator deletion
* Creator mentions
* Firefox-based authentication
* Docker application testing

---

# 35. Quick Start

```powershell
git clone https://github.com/JontySudha/MediaVault.git
cd MediaVault

python -m venv .venv
.venv\Scripts\activate

python -m pip install --upgrade pip
pip install -r requirements.txt

uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

Make sure Firefox is authenticated before attempting to discover protected content.

---

# MediaVault

**Discover → Download → Store → Organize → Synchronize**
