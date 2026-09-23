import json
import os
import subprocess
import threading

from app.task_control import (
    is_cancelled,
    register_process,
    unregister_process,
)


def _text_value(value, default=""):
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    return default


def _metadata_from_record(record):
    """Return (message_type, media_url, metadata) for gallery-dl JSON messages.

    gallery-dl uses message type 2 for directory metadata and type 3 for
    individual media URLs. Depending on gallery-dl version, directory
    messages may be emitted as [2, metadata] or [2, unused, metadata].
    """
    if not isinstance(record, list) or not record:
        return None, None, None

    message_type = record[0]

    if message_type == 2:
        if len(record) >= 3 and isinstance(record[2], dict):
            return 2, None, record[2]
        if len(record) >= 2 and isinstance(record[1], dict):
            return 2, None, record[1]
        return 2, None, {}

    if message_type == 3:
        media_url = record[1] if len(record) >= 2 else None
        metadata = record[2] if len(record) >= 3 and isinstance(record[2], dict) else {}
        return 3, _text_value(media_url), metadata

    return message_type, None, None


def normalize_gallery_post(record):
    """Convert a gallery-dl Directory/Url message into MediaVault format."""
    message_type, media_url, metadata = _metadata_from_record(record)

    if metadata is None or not isinstance(metadata, dict):
        return None

    tweet_id = metadata.get("tweet_id")
    if not tweet_id:
        return None
    tweet_id = str(tweet_id)

    author = metadata.get("author") or {}
    if isinstance(author, dict):
        username = (
            _text_value(author.get("screen_name"))
            or _text_value(author.get("username"))
            or _text_value(metadata.get("username"))
            or _text_value(metadata.get("user"))
            or "unknown"
        )
        creator = (
            _text_value(author.get("display_name"))
            or _text_value(author.get("name"))
            or _text_value(metadata.get("creator"))
            or username
        )
    else:
        username = (
            _text_value(metadata.get("username"))
            or _text_value(metadata.get("user"))
            or "unknown"
        )
        creator = _text_value(metadata.get("creator")) or username

    description = (
        _text_value(metadata.get("content"))
        or _text_value(metadata.get("description"))
    )

    upload_date = metadata.get("date") or metadata.get("datetime") or ""
    upload_date = str(upload_date)
    if len(upload_date) >= 10 and upload_date[4] == "-":
        upload_date = upload_date[:10].replace("-", "")
    elif len(upload_date) >= 8:
        upload_date = upload_date[:8]
    else:
        upload_date = ""

    post_url = (
        _text_value(metadata.get("url"))
        or f"https://x.com/{username}/status/{tweet_id}"
    )

    # Directory records contain post metadata. URL records contain the
    # actual downloadable media URL in record[1]. Some gallery-dl versions
    # also put URL/media_url into the metadata, so support both.
    if not media_url:
        for key in ("url", "media_url"):
            value = metadata.get(key)
            if isinstance(value, str) and value.startswith(("http://", "https://")):
                media_url = value
                break

    extension = _text_value(metadata.get("extension")) or None
    filename = _text_value(metadata.get("filename")) or None

    # For URL messages gallery-dl normally supplies these fields. If it
    # doesn't, derive a useful extension/name from the media URL.
    if media_url and not extension:
        clean_url = media_url.split("?", 1)[0]
        suffix = os.path.splitext(clean_url)[1]
        if suffix:
            extension = suffix.lstrip(".")

    if media_url and not filename:
        clean_url = media_url.split("?", 1)[0].rstrip("/")
        name = os.path.basename(clean_url)
        if name:
            filename = name

    return {
        "id": tweet_id,
        "post_id": tweet_id,
        "url": post_url,
        "post_url": post_url,
        "creator": creator,
        "creator_name": creator,
        "username": username,
        "description": description,
        "upload_date": upload_date,
        "date": upload_date,
        "media_url": media_url,
        "extension": extension,
        "filename": filename,
        "width": metadata.get("width"),
        "height": metadata.get("height"),
        "metadata": metadata,
        "message_type": message_type,
    }


def _terminate_process(process):
    if process is None:
        return

    try:
        if process.poll() is not None:
            return
    except Exception:
        return

    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            return
        except Exception:
            pass

    try:
        process.terminate()
    except Exception:
        pass

    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except Exception:
            pass
        try:
            process.wait(timeout=3)
        except Exception:
            pass


def _read_stderr(pipe, output):
    try:
        for line in pipe:
            output.append(line)
    except Exception:
        pass


def _iter_json_array(stream, creator_id=None):
    """Incrementally decode gallery-dl's JSON array."""
    decoder = json.JSONDecoder()
    buffer = ""
    position = 0
    started = False
    finished = False

    while not finished:
        if creator_id is not None and is_cancelled(creator_id):
            raise RuntimeError("Creator operation cancelled.")

        chunk = stream.read(65536)
        if chunk:
            buffer += chunk
        elif stream.closed:
            break

        while True:
            if creator_id is not None and is_cancelled(creator_id):
                raise RuntimeError("Creator operation cancelled.")

            while position < len(buffer) and buffer[position].isspace():
                position += 1

            if not started:
                if position >= len(buffer):
                    break
                if buffer[position] != "[":
                    raise RuntimeError("gallery-dl JSON output did not start with an array.")
                position += 1
                started = True
                continue

            while position < len(buffer) and buffer[position].isspace():
                position += 1

            if position >= len(buffer):
                break

            if buffer[position] == "]":
                position += 1
                finished = True
                break

            try:
                value, end = decoder.raw_decode(buffer, position)
            except json.JSONDecodeError:
                break

            position = end
            yield value

            while position < len(buffer) and buffer[position].isspace():
                position += 1

            if position < len(buffer) and buffer[position] == ",":
                position += 1
                continue

            if position < len(buffer) and buffer[position] == "]":
                position += 1
                finished = True
                break

            if position >= len(buffer):
                break

            raise RuntimeError("Invalid streaming JSON from gallery-dl.")

        if position > 0:
            buffer = buffer[position:]
            position = 0

        if finished:
            break

        if not chunk:
            break

    if not finished:
        raise RuntimeError("gallery-dl ended with incomplete JSON output.")


def _iter_gallery_records(profile_url, creator_id=None):
    command = [
        "gallery-dl",
        "--dump-json",
        "--cookies-from-browser",
        "firefox",
        f"{profile_url.rstrip('/')}/media",
    ]

    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    if creator_id is not None:
        register_process(creator_id, process)

    stderr_lines = []
    stderr_thread = threading.Thread(
        target=_read_stderr,
        args=(process.stderr, stderr_lines),
        daemon=True,
    )
    stderr_thread.start()

    try:
        for record in _iter_json_array(process.stdout, creator_id):
            yield record

        if creator_id is not None and is_cancelled(creator_id):
            _terminate_process(process)
            raise RuntimeError("Creator operation cancelled.")

        return_code = process.wait(timeout=10)

        if return_code != 0:
            error_text = "".join(stderr_lines).strip() or "gallery-dl failed."
            raise RuntimeError(f"gallery-dl failed: {error_text}")

    except Exception:
        if process.poll() is None:
            _terminate_process(process)
        raise

    finally:
        if creator_id is not None:
            unregister_process(creator_id, process)
        try:
            process.stdout.close()
        except Exception:
            pass
        try:
            process.stderr.close()
        except Exception:
            pass


def iter_gallery_posts(profile_url, limit=None, creator_id=None):
    """Yield posts and their media while gallery-dl is still discovering."""
    profile_url = profile_url.split("?", 1)[0].rstrip("/")

    if creator_id is not None and is_cancelled(creator_id):
        raise RuntimeError("Creator operation cancelled.")

    current = None
    count = 0

    for record in _iter_gallery_records(profile_url, creator_id):
        parsed = normalize_gallery_post(record)
        if not parsed:
            continue

        post_id = parsed["id"]

        # A directory message starts a post. URL messages belonging to that
        # post follow it and are added to its media list.
        if current is None or post_id != current["id"]:
            if current is not None:
                count += 1
                if limit is None or count <= limit:
                    yield current
                if limit is not None and count >= limit:
                    return

            current = dict(parsed)
            current["media"] = []

        # Keep the richest metadata from the directory message.
        if parsed.get("message_type") == 2:
            for key in (
                "creator",
                "creator_name",
                "username",
                "description",
                "upload_date",
                "date",
                "post_url",
            ):
                if parsed.get(key):
                    current[key] = parsed[key]

        media_url = parsed.get("media_url")
        if media_url:
            existing_urls = {item.get("url") for item in current["media"]}
            if media_url not in existing_urls:
                current["media"].append(
                    {
                        "url": media_url,
                        "extension": parsed.get("extension"),
                        "filename": parsed.get("filename"),
                        "width": parsed.get("width"),
                        "height": parsed.get("height"),
                    }
                )

    if current is not None:
        count += 1
        if limit is None or count <= limit:
            yield current

    print(f"[Gallery] Streamed {count} unique posts.")


def get_gallery_posts(profile_url, limit=None, creator_id=None):
    return list(iter_gallery_posts(profile_url, limit=limit, creator_id=creator_id))


def get_creator_posts(profile_url, creator_id=None):
    return get_gallery_posts(profile_url, limit=None, creator_id=creator_id)


def iter_creator_posts(profile_url, creator_id=None):
    return iter_gallery_posts(profile_url, limit=None, creator_id=creator_id)


def get_older_creator_posts(profile_url, limit=None, creator_id=None):
    return get_gallery_posts(profile_url, limit=limit, creator_id=creator_id)


def iter_older_creator_posts(profile_url, limit=None, creator_id=None):
    return iter_gallery_posts(profile_url, limit=limit, creator_id=creator_id)
