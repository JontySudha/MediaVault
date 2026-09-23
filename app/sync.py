from pathlib import Path
import json
import os
import time
import urllib.request
from urllib.parse import urlparse

from app.creator_downloader import iter_creator_posts
from app.database import (
    get_creator,
    get_post,
    add_post,
    add_media,
    update_creator_name,
    is_post_deleted,
)
from app.task_control import (
    start_task,
    finish_task,
    is_cancelled,
)


def detect_media_type(file):
    suffix = file.suffix.lower()
    if suffix in {".mp4", ".webm", ".mov", ".mkv"}:
        return "video"
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        return "image"
    if suffix in {".mp3", ".m4a", ".wav"}:
        return "audio"
    return "other"


def record_media_files(database_post_id, folder_path):
    folder_path = Path(folder_path)
    if not folder_path.exists():
        return 0

    count = 0
    for file in folder_path.iterdir():
        if not file.is_file():
            continue
        if file.name in {"metadata.json", "description.txt"}:
            continue
        if file.name.startswith(".downloading_"):
            continue

        add_media(
            database_post_id,
            file.name,
            detect_media_type(file),
            str(file),
        )
        count += 1
    return count


def _extension_from_url(media_url):
    try:
        suffix = Path(urlparse(media_url).path).suffix.lower()
        if suffix in {
            ".jpg", ".jpeg", ".png", ".gif", ".webp",
            ".mp4", ".webm", ".mov", ".mkv",
            ".mp3", ".m4a", ".wav",
        }:
            return suffix
    except Exception:
        pass
    return ""


def _extension_from_content_type(content_type):
    content_type = (content_type or "").split(";", 1)[0].strip().lower()
    return {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "video/mp4": ".mp4",
        "video/webm": ".webm",
        "video/quicktime": ".mov",
        "audio/mpeg": ".mp3",
        "audio/mp4": ".m4a",
        "audio/wav": ".wav",
        "audio/x-wav": ".wav",
    }.get(content_type, "")


def _normalise_extension(extension):
    extension = str(extension or "").strip().lower()
    if extension and not extension.startswith("."):
        extension = "." + extension

    allowed = {
        ".jpg", ".jpeg", ".png", ".gif", ".webp",
        ".mp4", ".webm", ".mov", ".mkv",
        ".mp3", ".m4a", ".wav",
    }
    return extension if extension in allowed else ""


def _replace_with_retry(temporary_path, output_path):
    last_error = None

    for _ in range(30):
        try:
            os.replace(str(temporary_path), str(output_path))
            return
        except PermissionError as error:
            last_error = error
            time.sleep(0.5)

    if last_error:
        raise last_error
    raise RuntimeError(f"Could not move {temporary_path} to {output_path}")


def download_gallery_media(post, post_folder, creator_id=None):
    """Download all media already discovered for one post."""
    post_folder = Path(post_folder)
    post_folder.mkdir(parents=True, exist_ok=True)

    media_items = post.get("media", []) or []
    downloaded_files = []

    for index, media in enumerate(media_items, start=1):
        if creator_id is not None and is_cancelled(creator_id):
            raise RuntimeError("Creator operation cancelled.")

        if not isinstance(media, dict):
            continue

        media_url = media.get("url")
        if not media_url:
            continue

        extension = _normalise_extension(media.get("extension"))
        if not extension:
            extension = _extension_from_url(media_url)

        filename = str(media.get("filename") or "").strip()
        if filename:
            filename = Path(filename).name
        else:
            filename = f"media_{index}"

        has_extension = bool(Path(filename).suffix)

        request = urllib.request.Request(
            media_url,
            headers={"User-Agent": "Mozilla/5.0"},
        )

        temporary_path = None
        output_path = None

        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                if not extension:
                    extension = _extension_from_content_type(
                        response.headers.get("Content-Type", "")
                    )

                if not extension:
                    extension = ".bin"

                if not has_extension:
                    filename += extension

                output_path = post_folder / filename

                if output_path.exists():
                    downloaded_files.append(output_path)
                    continue

                temporary_path = post_folder / f".downloading_{filename}"

                with open(temporary_path, "wb") as file:
                    while True:
                        if creator_id is not None and is_cancelled(creator_id):
                            raise RuntimeError("Creator operation cancelled.")

                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        file.write(chunk)

                    file.flush()
                    os.fsync(file.fileno())

            if creator_id is not None and is_cancelled(creator_id):
                raise RuntimeError("Creator operation cancelled.")

            _replace_with_retry(temporary_path, output_path)
            downloaded_files.append(output_path)

        except Exception:
            if temporary_path is not None and temporary_path.exists():
                for _ in range(10):
                    try:
                        temporary_path.unlink()
                        break
                    except PermissionError:
                        time.sleep(0.25)
                    except Exception:
                        break
            raise

    return downloaded_files


def save_post_metadata(post_folder, post):
    post_folder = Path(post_folder)
    with open(post_folder / "metadata.json", "w", encoding="utf-8") as file:
        json.dump(post, file, indent=4, ensure_ascii=False)

    with open(post_folder / "description.txt", "w", encoding="utf-8") as file:
        file.write(post.get("description", "") or "")


def remove_incomplete_downloads(post_folder):
    post_folder = Path(post_folder)
    if not post_folder.exists():
        return

    for file in post_folder.iterdir():
        if file.is_file() and file.name.startswith(".downloading_"):
            for _ in range(10):
                try:
                    file.unlink()
                    break
                except PermissionError:
                    time.sleep(0.25)
                except Exception:
                    break


def _safe_folder_name(value):
    import re
    value = str(value or "unknown_creator")
    value = re.sub(r'[<>:"/\\|?*]', "_", value).strip().rstrip(".")
    return value[:100] or "unknown_creator"


def _post_folder(creator_name, upload_date, post_id):
    if len(str(upload_date or "")) == 8:
        date_folder = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"
    else:
        date_folder = "unknown_date"

    return (
        Path("gallery")
        / _safe_folder_name(creator_name)
        / date_folder
        / f"post_{_safe_folder_name(post_id)}"
    )


def _string_value(value, fallback=""):
    if isinstance(value, dict):
        return str(
            value.get("name")
            or value.get("display_name")
            or value.get("screen_name")
            or value.get("username")
            or fallback
        )
    if isinstance(value, list):
        return fallback
    return str(value or fallback)


def _process_post(creator, post, creator_id, results):
    if is_cancelled(creator_id):
        return False

    post_id = str(post.get("id") or post.get("post_id") or "")
    if not post_id:
        return True

    if is_post_deleted(creator_id, post_id):
        return True

    existing_post = get_post(creator_id, post_id)

    creator_name = _string_value(
        post.get("creator")
        or post.get("creator_name")
        or creator.get("display_name")
        or creator.get("username"),
        "unknown_creator",
    )

    username = _string_value(
        post.get("username") or creator.get("username"),
        "",
    )

    update_creator_name(creator_id, creator_name, username)

    if existing_post:
        post_folder = Path(
            existing_post.get("folder_path")
            or _post_folder(
                creator_name,
                post.get("upload_date") or post.get("date") or "",
                post_id,
            )
        )

        try:
            download_gallery_media(post, post_folder, creator_id=creator_id)
            if is_cancelled(creator_id):
                remove_incomplete_downloads(post_folder)
                return False

            save_post_metadata(post_folder, post)
            record_media_files(existing_post["id"], post_folder)
        except Exception:
            remove_incomplete_downloads(post_folder)
            raise

        return True

    post_folder = _post_folder(
        creator_name,
        post.get("upload_date") or post.get("date") or "",
        post_id,
    )
    post_folder.mkdir(parents=True, exist_ok=True)

    try:
        download_gallery_media(post, post_folder, creator_id=creator_id)

        if is_cancelled(creator_id):
            remove_incomplete_downloads(post_folder)
            return False

        save_post_metadata(post_folder, post)

        if is_cancelled(creator_id):
            remove_incomplete_downloads(post_folder)
            return False

        database_post_id = add_post(
            creator_id,
            post_id,
            post.get("post_url") or post.get("url") or "",
            post.get("description") or "",
            post.get("upload_date") or post.get("date") or "",
            str(post_folder),
        )

        record_media_files(database_post_id, post_folder)

        results.append({
            "post_id": post_id,
            "folder": str(post_folder),
        })
        return True

    except Exception:
        remove_incomplete_downloads(post_folder)
        if is_cancelled(creator_id):
            return False
        raise


def sync_creator(creator_id):
    creator = get_creator(creator_id)
    if not creator:
        return {
            "success": False,
            "cancelled": False,
            "message": "Creator not found.",
            "discovered": 0,
            "new_posts": 0,
            "results": [],
        }

    start_task(creator_id)
    results = []
    discovered = 0

    try:
        if is_cancelled(creator_id):
            return {
                "success": False,
                "cancelled": True,
                "discovered": 0,
                "new_posts": 0,
                "results": [],
            }

        profile_url = creator["profile_url"]

        for post in iter_creator_posts(
            profile_url,
            creator_id=creator_id,
        ):
            if is_cancelled(creator_id):
                break

            discovered += 1
            _process_post(
                creator,
                post,
                creator_id,
                results,
            )

        cancelled = is_cancelled(creator_id)
        return {
            "success": not cancelled,
            "cancelled": cancelled,
            "discovered": discovered,
            "new_posts": len(results),
            "results": results,
        }

    finally:
        finish_task(creator_id)
