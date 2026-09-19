from pathlib import Path
import sqlite3


DATABASE_DIR = Path("database")
DATABASE_DIR.mkdir(exist_ok=True)

DATABASE_PATH = DATABASE_DIR / "media.db"


def get_connection():

    connection = sqlite3.connect(
        DATABASE_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


def init_database():

    connection = get_connection()

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS creators (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            platform TEXT NOT NULL,

            username TEXT,

            profile_url TEXT NOT NULL UNIQUE,

            display_name TEXT,

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

            UNIQUE(
                creator_id,
                platform_post_id
            ),

            FOREIGN KEY (creator_id)
                REFERENCES creators(id)
                ON DELETE CASCADE
        );


        CREATE TABLE IF NOT EXISTS media (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            post_id INTEGER NOT NULL,

            filename TEXT NOT NULL,

            media_type TEXT,

            file_path TEXT,

            UNIQUE(
                post_id,
                filename
            ),

            FOREIGN KEY (post_id)
                REFERENCES posts(id)
                ON DELETE CASCADE
        );


        CREATE UNIQUE INDEX IF NOT EXISTS
        idx_media_post_filename
        ON media(post_id, filename);
        """
    )

    connection.commit()

    connection.close()


def add_creator(
    platform,
    username,
    profile_url,
    display_name=None
):

    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO creators
        (
            platform,
            username,
            profile_url,
            display_name
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            platform,
            username,
            profile_url,
            display_name
        )
    )

    connection.commit()

    creator_id = cursor.lastrowid

    if creator_id == 0:

        row = connection.execute(
            """
            SELECT id
            FROM creators
            WHERE profile_url = ?
            """,
            (profile_url,)
        ).fetchone()

        creator_id = row["id"]

    connection.close()

    return creator_id


def update_creator_name(
    creator_id,
    display_name,
    username=None
):

    connection = get_connection()

    if username:

        connection.execute(
            """
            UPDATE creators
            SET display_name = ?,
                username = ?
            WHERE id = ?
            """,
            (
                display_name,
                username,
                creator_id
            )
        )

    else:

        connection.execute(
            """
            UPDATE creators
            SET display_name = ?
            WHERE id = ?
            """,
            (
                display_name,
                creator_id
            )
        )

    connection.commit()

    connection.close()


def get_creators():

    connection = get_connection()

    creators = connection.execute(
        """
        SELECT *
        FROM creators
        ORDER BY created_at DESC
        """
    ).fetchall()

    connection.close()

    return [
        dict(creator)
        for creator in creators
    ]


def get_enabled_creators():

    connection = get_connection()

    creators = connection.execute(
        """
        SELECT *
        FROM creators
        WHERE enabled = 1
        ORDER BY created_at DESC
        """
    ).fetchall()

    connection.close()

    return [
        dict(creator)
        for creator in creators
    ]


def get_creator(creator_id):

    connection = get_connection()

    creator = connection.execute(
        """
        SELECT *
        FROM creators
        WHERE id = ?
        """,
        (creator_id,)
    ).fetchone()

    connection.close()

    if creator:
        return dict(creator)

    return None


def get_posts():

    connection = get_connection()

    posts = connection.execute(
        """
        SELECT
            posts.*,
            creators.username,
            creators.display_name
        FROM posts
        JOIN creators
            ON posts.creator_id = creators.id
        ORDER BY
    posts.created_at DESC,
    posts.downloaded_at DESC
        """
    ).fetchall()

    connection.close()

    return [
        dict(post)
        for post in posts
    ]


def get_creator_posts(creator_id):

    connection = get_connection()

    posts = connection.execute(
        """
        SELECT
            posts.*,
            creators.username,
            creators.display_name
        FROM posts
        JOIN creators
            ON posts.creator_id = creators.id
        WHERE posts.creator_id = ?
        ORDER BY
    posts.created_at DESC,
    posts.downloaded_at DESC
        """,
        (creator_id,)
    ).fetchall()

    connection.close()

    return [
        dict(post)
        for post in posts
    ]


def get_post(
    creator_id,
    platform_post_id
):

    connection = get_connection()

    post = connection.execute(
        """
        SELECT *
        FROM posts
        WHERE creator_id = ?
        AND platform_post_id = ?
        """,
        (
            creator_id,
            platform_post_id
        )
    ).fetchone()

    connection.close()

    if post:
        return dict(post)

    return None


def add_post(
    creator_id,
    platform_post_id,
    post_url,
    description,
    created_at,
    folder_path
):

    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO posts
        (
            creator_id,
            platform_post_id,
            post_url,
            description,
            created_at,
            folder_path
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            creator_id,
            platform_post_id,
            post_url,
            description,
            created_at,
            folder_path
        )
    )

    connection.commit()

    post_id = cursor.lastrowid

    if post_id == 0:

        row = connection.execute(
            """
            SELECT id
            FROM posts
            WHERE creator_id = ?
            AND platform_post_id = ?
            """,
            (
                creator_id,
                platform_post_id
            )
        ).fetchone()

        post_id = row["id"]

    connection.close()

    return post_id


def add_media(
    post_id,
    filename,
    media_type,
    file_path
):

    connection = get_connection()

    cursor = connection.execute(
        """
        INSERT OR IGNORE INTO media
        (
            post_id,
            filename,
            media_type,
            file_path
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            post_id,
            filename,
            media_type,
            file_path
        )
    )

    connection.commit()

    media_id = cursor.lastrowid

    if media_id == 0:

        row = connection.execute(
            """
            SELECT id
            FROM media
            WHERE post_id = ?
            AND filename = ?
            """,
            (
                post_id,
                filename
            )
        ).fetchone()

        media_id = row["id"]

    connection.close()

    return media_id


def get_media(post_id):

    connection = get_connection()

    media = connection.execute(
        """
        SELECT *
        FROM media
        WHERE post_id = ?
        ORDER BY id ASC
        """,
        (post_id,)
    ).fetchall()

    connection.close()

    return [
        dict(item)
        for item in media
    ]


def get_all_media():

    connection = get_connection()

    media = connection.execute(
        """
        SELECT
            media.*,
            posts.platform_post_id,
            posts.post_url
        FROM media
        JOIN posts
            ON media.post_id = posts.id
        ORDER BY media.id DESC
        """
    ).fetchall()

    connection.close()

    return [
        dict(item)
        for item in media
    ]
def delete_post(post_id):
    connection = get_connection()

    connection.execute(
        """
        DELETE FROM posts
        WHERE id = ?
        """,
        (post_id,)
    )

    connection.commit()
    connection.close()


def delete_creator(creator_id):
    connection = get_connection()

    connection.execute(
        """
        DELETE FROM creators
        WHERE id = ?
        """,
        (creator_id,)
    )

    connection.commit()
    connection.close()
    
def get_post_by_id(post_id):

    connection = get_connection()

    post = connection.execute(
        """
        SELECT *
        FROM posts
        WHERE id = ?
        """,
        (post_id,)
    ).fetchone()

    connection.close()

    if post:
        return dict(post)

    return None