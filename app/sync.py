from pathlib import Path

from app.creator_downloader import get_creator_posts

from app.database import (
    get_creator,
    get_post,
    add_post,
    add_media,
    update_creator_name,
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


def record_media_files(
    database_post_id,
    folder_path,
):
    if not folder_path.exists():
        return

    for file in folder_path.iterdir():

        if not file.is_file():
            continue

        if file.name in {
            "metadata.json",
            "description.txt",
        }:
            continue

        add_media(
            post_id=database_post_id,
            filename=file.name,
            media_type=detect_media_type(file),
            file_path=str(file),
        )


def download_gallery_media(
    post,
    post_folder,
):
    """
    Download media URLs discovered by gallery-dl.
    """

    import urllib.request

    downloaded_files = []

    media_items = post.get(
        "media",
        []
    )

    for index, media in enumerate(
        media_items,
        start=1,
    ):

        media_url = media.get("url")

        if not media_url:
            continue

        extension = (
            media.get("extension")
            or "bin"
        )

        filename = (
            media.get("filename")
            or f"media_{index}"
        )

        filename = str(filename)

        if "." not in filename:
            filename = (
                f"{filename}.{extension}"
            )

        output_path = (
            post_folder / filename
        )

        if output_path.exists():
            downloaded_files.append(
                output_path
            )
            continue

        request = urllib.request.Request(
            media_url,
            headers={
                "User-Agent": "Mozilla/5.0",
            },
        )

        with urllib.request.urlopen(
            request
        ) as response:

            with open(
                output_path,
                "wb",
            ) as file:

                file.write(
                    response.read()
                )

        downloaded_files.append(
            output_path
        )

    return downloaded_files


def save_post_metadata(
    post_folder,
    post,
):
    import json

    metadata = {
        "platform": "X",
        "post_id": post.get("id"),
        "post_url": post.get("url"),
        "creator": post.get("creator"),
        "username": post.get("username"),
        "description": post.get("description"),
        "upload_date": post.get("upload_date"),
        "media_type": post.get("media_type"),
        "media": post.get("media", []),
    }

    with open(
        post_folder / "metadata.json",
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            metadata,
            file,
            indent=4,
            ensure_ascii=False,
        )

    with open(
        post_folder / "description.txt",
        "w",
        encoding="utf-8",
    ) as file:

        file.write(
            post.get("description")
            or ""
        )


def sync_creator(
    creator_id: int,
):
    """
    Synchronize recent X posts using
    authenticated gallery-dl discovery.
    """

    creator = get_creator(
        creator_id
    )

    if not creator:
        raise ValueError(
            f"Creator {creator_id} does not exist."
        )

    profile_url = creator[
        "profile_url"
    ]

    discovered_posts = get_creator_posts(
        profile_url
    )

    results = []

    for discovered_post in discovered_posts:

        discovered_id = str(
            discovered_post["id"]
        )

        post_url = discovered_post[
            "url"
        ]

        existing_post = get_post(
            creator_id,
            discovered_id,
        )

        if existing_post:

            if existing_post.get(
                "folder_path"
            ):

                record_media_files(
                    existing_post["id"],
                    Path(
                        existing_post[
                            "folder_path"
                        ]
                    ),
                )

            results.append({
                "post_id": discovered_id,
                "url": post_url,
                "status": "skipped",
                "reason": "Already in database",
            })

            continue

        try:

            creator_name = (
                discovered_post.get(
                    "creator"
                )
                or creator.get(
                    "display_name"
                )
                or creator.get(
                    "username"
                )
                or "unknown_creator"
            )

            username = (
                discovered_post.get(
                    "username"
                )
                or creator.get(
                    "username"
                )
            )

            update_creator_name(
                creator_id,
                creator_name,
                username,
            )

            upload_date = (
                discovered_post.get(
                    "upload_date"
                )
                or ""
            )

            if len(upload_date) == 8:

                date_folder = (
                    f"{upload_date[:4]}-"
                    f"{upload_date[4:6]}-"
                    f"{upload_date[6:8]}"
                )

            else:

                date_folder = (
                    "unknown_date"
                )

            post_folder = (
                Path("gallery")
                / creator_name
                / date_folder
                / f"post_{discovered_id}"
            )

            post_folder.mkdir(
                parents=True,
                exist_ok=True,
            )

            print(
                f"\n[Sync] Downloading:"
                f" {discovered_id}"
            )

            downloaded_files = (
                download_gallery_media(
                    discovered_post,
                    post_folder,
                )
            )

            save_post_metadata(
                post_folder,
                discovered_post,
            )

            database_post_id = add_post(
                creator_id=creator_id,
                platform_post_id=discovered_id,
                post_url=post_url,
                description=(
                    discovered_post.get(
                        "description"
                    )
                    or ""
                ),
                created_at=upload_date,
                folder_path=str(
                    post_folder
                ),
            )

            record_media_files(
                database_post_id,
                post_folder,
            )

            results.append({
                "post_id": discovered_id,
                "url": post_url,
                "status": "downloaded",
                "media_type": (
                    discovered_post.get(
                        "media_type"
                    )
                    or "unknown"
                ),
                "files": len(
                    downloaded_files
                ),
                "database_id": (
                    database_post_id
                ),
            })

        except Exception as error:

            results.append({
                "post_id": discovered_id,
                "url": post_url,
                "status": "error",
                "error": str(error),
            })

            print(
                f"[Sync] Error "
                f"{discovered_id}: {error}"
            )

    return {
        "creator_id": creator_id,
        "profile_url": profile_url,
        "discovered": len(
            discovered_posts
        ),
        "results": results,
    }