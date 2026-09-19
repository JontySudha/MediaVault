from pathlib import Path

from app.database import (
    get_posts,
    get_media,
    add_media,
)


def detect_media_type(file):

    suffix = file.suffix.lower()

    if suffix in {
        ".mp4",
        ".webm",
        ".mov",
        ".mkv",
    }:
        return "video"

    if suffix in {
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
    }:
        return "image"

    if suffix in {
        ".mp3",
        ".m4a",
        ".wav",
    }:
        return "audio"

    return "other"


posts = get_posts()

print(
    f"Found {len(posts)} posts."
)

for post in posts:

    post_id = post["id"]

    existing_media = get_media(
        post_id
    )

    if existing_media:

        print(
            f"Post {post_id}: already migrated"
        )

        continue

    folder_path = post.get(
        "folder_path"
    )

    if not folder_path:

        print(
            f"Post {post_id}: no folder path"
        )

        continue

    folder = Path(
        folder_path
    )

    if not folder.exists():

        print(
            f"Post {post_id}: folder not found:"
        )

        print(
            f"  {folder}"
        )

        continue

    files = [
        file
        for file in folder.iterdir()
        if file.is_file()
        and file.name not in {
            "metadata.json",
            "description.txt",
        }
    ]

    if not files:

        print(
            f"Post {post_id}: no media files"
        )

        continue

    for file in files:

        media_type = detect_media_type(
            file
        )

        add_media(
            post_id=post_id,
            filename=file.name,
            media_type=media_type,
            file_path=str(file),
        )

        print(
            f"Post {post_id}: added "
            f"{file.name} ({media_type})"
        )

print(
    "\nMigration complete."
)
