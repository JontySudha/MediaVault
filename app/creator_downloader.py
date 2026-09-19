import json
import re
import subprocess


def normalize_gallery_post(record):
    """
    Convert one gallery-dl JSON record
    into a MediaVault post structure.
    """

    if not isinstance(record, list):
        return None

    if len(record) < 2:
        return None

    media_url = None
    metadata = None

    if len(record) >= 3 and isinstance(record[2], dict):
        media_url = record[1]
        metadata = record[2]

    elif isinstance(record[1], dict):
        metadata = record[1]

    if not metadata:
        return None

    tweet_id = (
        metadata.get("tweet_id")
        or metadata.get("conversation_id")
    )

    if not tweet_id:
        return None

    tweet_id = str(tweet_id)

    author = metadata.get("author") or {}
    user = metadata.get("user") or {}

    username = (
        user.get("nick")
        or author.get("nick")
        or user.get("name")
        or author.get("name")
        or "unknown"
    )

    creator_name = (
        author.get("nick")
        or user.get("nick")
        or author.get("name")
        or user.get("name")
        or username
    )

    description = (
        metadata.get("content")
        or metadata.get("description")
        or ""
    )

    date_value = metadata.get("date") or ""

    upload_date = ""

    date_match = re.search(
        r"(\d{4})-(\d{2})-(\d{2})",
        str(date_value)
    )

    if date_match:
        upload_date = (
            f"{date_match.group(1)}"
            f"{date_match.group(2)}"
            f"{date_match.group(3)}"
        )

    post_url = (
        f"https://x.com/"
        f"{username}/status/"
        f"{tweet_id}"
    )

    media_type = metadata.get("type") or "unknown"

    return {
        "id": tweet_id,
        "url": post_url,
        "title": "",
        "description": description,
        "upload_date": upload_date,
        "creator": creator_name,
        "username": username,
        "media_type": media_type,
        "media_url": media_url,
        "extension": metadata.get("extension"),
        "filename": metadata.get("filename"),
        "width": metadata.get("width"),
        "height": metadata.get("height"),
        "metadata": metadata,
    }


def get_gallery_posts(
    profile_url: str,
    limit: int = 100,
):
    """
    Get authenticated X posts using gallery-dl.
    """

    profile_url = (
        profile_url
        .strip()
        .split("?", 1)[0]
        .rstrip("/")
    )

    command = [
        "gallery-dl",
        "--dump-json",
        "--cookies-from-browser",
        "firefox",
        profile_url + "/media",
    ]

    print("\n[Gallery] Starting authenticated X discovery:")
    print(profile_url)

    try:

        process = subprocess.run(
            command,
            capture_output=True,
            timeout=600,
        )

    except subprocess.TimeoutExpired:

        raise RuntimeError(
            "gallery-dl timed out while reading X."
        )

    stdout = process.stdout

    stderr = process.stderr.decode(
        "utf-8",
        errors="replace",
    )

    if process.returncode != 0:

        raise RuntimeError(
            stderr.strip()
            or "gallery-dl failed."
        )

    if not stdout:
        return []

    try:

        records = json.loads(
            stdout.decode(
                "utf-8",
                errors="replace",
            )
        )

    except json.JSONDecodeError as error:

        raise RuntimeError(
            f"Could not parse gallery-dl output: {error}"
        )

    posts_by_id = {}

    for record in records:

        post = normalize_gallery_post(record)

        if not post:
            continue

        post_id = post["id"]

        if post_id not in posts_by_id:

            posts_by_id[post_id] = {
                "id": post_id,
                "url": post["url"],
                "title": post["title"],
                "description": post["description"],
                "upload_date": post["upload_date"],
                "creator": post["creator"],
                "username": post["username"],
                "media_type": post["media_type"],
                "media": [],
                "metadata": post["metadata"],
            }

        if post.get("media_url"):

            posts_by_id[post_id]["media"].append({
                "url": post["media_url"],
                "type": post.get("media_type"),
                "extension": post.get("extension"),
                "filename": post.get("filename"),
                "width": post.get("width"),
                "height": post.get("height"),
            })

            if (
                posts_by_id[post_id]["media_type"]
                == "unknown"
            ):
                posts_by_id[post_id]["media_type"] = (
                    post.get("media_type")
                    or "unknown"
                )

    posts = list(posts_by_id.values())

    posts.sort(
        key=lambda post: (
            post.get("upload_date") or ""
        ),
        reverse=True,
    )

    if limit:
        posts = posts[:limit]

    print(
        f"[Gallery] Found {len(posts)} unique posts."
    )

    return posts


def get_creator_posts(profile_url: str):
    """
    Get recent posts using authenticated gallery-dl.
    """

    return get_gallery_posts(
        profile_url,
        limit=30,
    )


def get_older_creator_posts(
    profile_url: str,
    limit: int = 100,
):
    """
    Get older posts using authenticated gallery-dl.
    """

    return get_gallery_posts(
        profile_url,
        limit=limit,
    )