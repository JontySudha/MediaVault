from pathlib import Path
import json
import sqlite3
from threading import RLock


DATABASE_DIR = Path("database")
DATABASE_DIR.mkdir(exist_ok=True)
DATABASE_PATH = DATABASE_DIR / "media.db"

# SQLite allows multiple readers, but writes can briefly block each other.
# Keep one process-local write lock and make SQLite wait for other writers.
_db_write_lock = RLock()


def get_connection():
    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 30000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


def init_database():
    with _db_write_lock:
        connection = get_connection()
        try:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS creators (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    username TEXT,
                    profile_url TEXT NOT NULL UNIQUE,
                    display_name TEXT,
                    profile_description TEXT DEFAULT '',
                    profile_photo_url TEXT DEFAULT '',
                    profile_links TEXT DEFAULT '[]',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    enabled INTEGER DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    creator_id INTEGER NOT NULL,
                    platform_post_id TEXT NOT NULL,
                    post_url TEXT NOT NULL,
                    description TEXT,
                    created_at TEXT,
                    downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    folder_path TEXT,
                    UNIQUE(creator_id, platform_post_id),
                    FOREIGN KEY (creator_id) REFERENCES creators(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS media (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    media_type TEXT,
                    file_path TEXT,
                    UNIQUE(post_id, filename),
                    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS deleted_posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    creator_id INTEGER NOT NULL,
                    platform_post_id TEXT NOT NULL,
                    deleted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(creator_id, platform_post_id),
                    FOREIGN KEY (creator_id) REFERENCES creators(id) ON DELETE CASCADE
                );

                CREATE UNIQUE INDEX IF NOT EXISTS idx_media_post_filename
                ON media(post_id, filename);

                CREATE INDEX IF NOT EXISTS idx_deleted_posts_creator_platform
                ON deleted_posts(creator_id, platform_post_id);
                """
            )

            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(creators)").fetchall()
            }

            migrations = {
                "profile_description": "ALTER TABLE creators ADD COLUMN profile_description TEXT DEFAULT ''",
                "profile_photo_url": "ALTER TABLE creators ADD COLUMN profile_photo_url TEXT DEFAULT ''",
                "profile_links": "ALTER TABLE creators ADD COLUMN profile_links TEXT DEFAULT '[]'",
            }

            for column, statement in migrations.items():
                if column not in columns:
                    connection.execute(statement)

            connection.commit()
        finally:
            connection.close()


def add_creator(platform, username, profile_url, display_name=None):
    with _db_write_lock:
        connection = get_connection()
        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO creators
                (platform, username, profile_url, display_name)
                VALUES (?, ?, ?, ?)
                """,
                (platform, username, profile_url, display_name),
            )
            connection.commit()
            creator_id = cursor.lastrowid

            if creator_id == 0:
                row = connection.execute(
                    "SELECT id FROM creators WHERE profile_url = ?",
                    (profile_url,),
                ).fetchone()
                creator_id = row["id"]

            return creator_id
        finally:
            connection.close()


def update_creator_name(creator_id, display_name, username=None):
    with _db_write_lock:
        connection = get_connection()
        try:
            if username:
                connection.execute(
                    "UPDATE creators SET display_name = ?, username = ? WHERE id = ?",
                    (display_name, username, creator_id),
                )
            else:
                connection.execute(
                    "UPDATE creators SET display_name = ? WHERE id = ?",
                    (display_name, creator_id),
                )
            connection.commit()
        finally:
            connection.close()


def update_creator_profile_description(creator_id, description):
    with _db_write_lock:
        connection = get_connection()
        try:
            connection.execute(
                "UPDATE creators SET profile_description = ? WHERE id = ?",
                (description or "", creator_id),
            )
            connection.commit()
        finally:
            connection.close()


def update_creator_profile_photo(creator_id, photo_url):
    with _db_write_lock:
        connection = get_connection()
        try:
            connection.execute(
                "UPDATE creators SET profile_photo_url = ? WHERE id = ?",
                (photo_url or "", creator_id),
            )
            connection.commit()
        finally:
            connection.close()


def update_creator_profile_links(creator_id, links):
    clean_links = []
    seen = set()

    for item in links or []:
        if isinstance(item, dict):
            url = str(item.get("url") or "").strip()
            label = str(item.get("label") or "").strip()
        else:
            url = str(item or "").strip()
            label = ""

        if not url.startswith(("http://", "https://")) or url in seen:
            continue

        seen.add(url)
        clean_links.append({"label": label, "url": url})

    with _db_write_lock:
        connection = get_connection()
        try:
            connection.execute(
                "UPDATE creators SET profile_links = ? WHERE id = ?",
                (json.dumps(clean_links, ensure_ascii=False), creator_id),
            )
            connection.commit()
        finally:
            connection.close()


def _decode_links(value):
    try:
        links = json.loads(value or "[]")
    except (TypeError, ValueError, json.JSONDecodeError):
        return []

    result = []
    for item in links:
        if isinstance(item, dict):
            url = str(item.get("url") or "").strip()
            label = str(item.get("label") or "").strip()
            if url:
                result.append({"label": label, "url": url})
        elif isinstance(item, str) and item.strip():
            result.append({"label": "", "url": item.strip()})

    return result


def get_creator_profile_links(creator):
    if not creator:
        return []
    return _decode_links(creator.get("profile_links"))


def get_creators():
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM creators ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_enabled_creators():
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM creators WHERE enabled = 1 ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_creator(creator_id):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT * FROM creators WHERE id = ?",
            (creator_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def get_posts():
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT posts.*, creators.username, creators.display_name
            FROM posts
            JOIN creators ON posts.creator_id = creators.id
            ORDER BY posts.created_at DESC, posts.downloaded_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_creator_posts(creator_id):
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT posts.*, creators.username, creators.display_name
            FROM posts
            JOIN creators ON posts.creator_id = creators.id
            WHERE posts.creator_id = ?
            ORDER BY posts.created_at DESC, posts.downloaded_at DESC
            """,
            (creator_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_post(creator_id, platform_post_id):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT * FROM posts
            WHERE creator_id = ? AND platform_post_id = ?
            """,
            (creator_id, str(platform_post_id)),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def is_post_deleted(creator_id, platform_post_id):
    connection = get_connection()
    try:
        row = connection.execute(
            """
            SELECT 1 FROM deleted_posts
            WHERE creator_id = ? AND platform_post_id = ?
            LIMIT 1
            """,
            (creator_id, str(platform_post_id)),
        ).fetchone()
        return row is not None
    finally:
        connection.close()


def mark_post_deleted(creator_id, platform_post_id):
    with _db_write_lock:
        connection = get_connection()
        try:
            connection.execute(
                """
                INSERT OR IGNORE INTO deleted_posts (creator_id, platform_post_id)
                VALUES (?, ?)
                """,
                (creator_id, str(platform_post_id)),
            )
            connection.commit()
        finally:
            connection.close()


def unmark_post_deleted(creator_id, platform_post_id):
    with _db_write_lock:
        connection = get_connection()
        try:
            connection.execute(
                """
                DELETE FROM deleted_posts
                WHERE creator_id = ? AND platform_post_id = ?
                """,
                (creator_id, str(platform_post_id)),
            )
            connection.commit()
        finally:
            connection.close()


def add_post(creator_id, platform_post_id, post_url, description, created_at, folder_path):
    with _db_write_lock:
        connection = get_connection()
        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO posts
                (creator_id, platform_post_id, post_url, description, created_at, folder_path)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    creator_id,
                    str(platform_post_id),
                    post_url or "",
                    description or "",
                    created_at or "",
                    folder_path,
                ),
            )
            connection.commit()
            post_id = cursor.lastrowid

            if post_id == 0:
                row = connection.execute(
                    """
                    SELECT id FROM posts
                    WHERE creator_id = ? AND platform_post_id = ?
                    """,
                    (creator_id, str(platform_post_id)),
                ).fetchone()
                post_id = row["id"]

            return post_id
        finally:
            connection.close()


def add_media(post_id, filename, media_type, file_path):
    with _db_write_lock:
        connection = get_connection()
        try:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO media (post_id, filename, media_type, file_path)
                VALUES (?, ?, ?, ?)
                """,
                (post_id, filename, media_type, file_path),
            )
            connection.commit()
            media_id = cursor.lastrowid

            if media_id == 0:
                row = connection.execute(
                    "SELECT id FROM media WHERE post_id = ? AND filename = ?",
                    (post_id, filename),
                ).fetchone()
                media_id = row["id"]

            return media_id
        finally:
            connection.close()


def get_media(post_id):
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT * FROM media WHERE post_id = ? ORDER BY id ASC",
            (post_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_all_media():
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT media.*, posts.platform_post_id, posts.post_url
            FROM media
            JOIN posts ON media.post_id = posts.id
            ORDER BY media.id DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def get_post_by_id(post_id):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT * FROM posts WHERE id = ?",
            (post_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def delete_post(post_id):
    with _db_write_lock:
        connection = get_connection()
        try:
            post = connection.execute(
                "SELECT creator_id, platform_post_id FROM posts WHERE id = ?",
                (post_id,),
            ).fetchone()
            if post:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO deleted_posts (creator_id, platform_post_id)
                    VALUES (?, ?)
                    """,
                    (post["creator_id"], str(post["platform_post_id"])),
                )
                connection.execute("DELETE FROM posts WHERE id = ?", (post_id,))
            connection.commit()
        finally:
            connection.close()


def delete_creator(creator_id):
    with _db_write_lock:
        connection = get_connection()
        try:
            connection.execute("DELETE FROM creators WHERE id = ?", (creator_id,))
            connection.commit()
        finally:
            connection.close()
