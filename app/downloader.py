from pathlib import Path
import json
import re
import urllib.request

import yt_dlp


GALLERY_DIR = Path("gallery")


def safe_name(name: str) -> str:

    name = name or "unknown_creator"

    name = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        name
    )

    name = name.strip().rstrip(".")

    return name[:100]


def get_x_page(url: str):

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(request) as response:

        html = response.read().decode(
            "utf-8",
            errors="ignore"
        )

    return html


def download_image(
    image_url: str,
    output_path: Path
):

    request = urllib.request.Request(
        image_url,
        headers={
            "User-Agent": "Mozilla/5.0"
        }
    )

    with urllib.request.urlopen(request) as response:

        with open(
            output_path,
            "wb"
        ) as file:

            file.write(
                response.read()
            )


def extract_x_fallback_metadata(
    url: str,
    html: str
):

    post_id_match = re.search(
        r"/status/(\d+)",
        url
    )

    post_id = (
        post_id_match.group(1)
        if post_id_match
        else "unknown_post"
    )

    display_name = None

    creator_patterns = [
        r'"author_name":"([^"]+)"',
        r'"name":"([^"]+)","screen_name"',
        r'"display_name":"([^"]+)"',
    ]

    for pattern in creator_patterns:

        match = re.search(
            pattern,
            html
        )

        if match:

            display_name = match.group(1)

            break

    profile_url = url.split(
        "/status/",
        1
    )[0].rstrip("/")

    username = (
        profile_url.split("/")[-1]
    )

    creator = safe_name(
        display_name
        or username
        or "unknown_creator"
    )

    description = ""

    description_patterns = [
        r'<meta name="description" content="([^"]*)"',
        r'<meta property="og:description" content="([^"]*)"',
    ]

    for pattern in description_patterns:

        match = re.search(
            pattern,
            html,
            re.IGNORECASE
        )

        if match:

            description = (
                match.group(1)
                .replace("&quot;", '"')
                .replace("&#39;", "'")
                .replace("&amp;", "&")
            )

            break

    upload_date = ""

    date_patterns = [
        r'"created_at":"([^"]+)"',
        r'"datePublished":"([^"]+)"',
    ]

    for pattern in date_patterns:

        match = re.search(
            pattern,
            html
        )

        if match:

            raw_date = match.group(1)

            date_match = re.search(
                r'(\d{4})-(\d{2})-(\d{2})',
                raw_date
            )

            if date_match:

                upload_date = (
                    f"{date_match.group(1)}"
                    f"{date_match.group(2)}"
                    f"{date_match.group(3)}"
                )

                break

    return {
        "platform": "X",
        "post_id": post_id,
        "creator": creator,
        "username": username,
        "description": description,
        "upload_date": upload_date,
        "post_url": url,
        "webpage_url": url,
    }


def create_post_folder(
    creator: str,
    upload_date: str,
    post_id: str
):

    if len(upload_date) == 8:

        date_folder = (
            f"{upload_date[:4]}-"
            f"{upload_date[4:6]}-"
            f"{upload_date[6:8]}"
        )

    else:

        date_folder = "unknown_date"

    post_folder = (
        GALLERY_DIR
        / safe_name(creator)
        / date_folder
        / f"post_{safe_name(post_id)}"
    )

    post_folder.mkdir(
        parents=True,
        exist_ok=True
    )

    return post_folder


def save_metadata(
    post_folder: Path,
    metadata: dict
):

    with open(
        post_folder / "metadata.json",
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            metadata,
            file,
            indent=4,
            ensure_ascii=False
        )

    with open(
        post_folder / "description.txt",
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            metadata.get(
                "description",
                ""
            )
        )


def extract_video_metadata(url: str):

    options = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "cookiesfrombrowser": ("firefox",),
    }

    with yt_dlp.YoutubeDL(options) as ydl:

        info = ydl.extract_info(
            url,
            download=False
        )

    creator = safe_name(
        info.get("uploader")
        or info.get("channel")
        or info.get("creator")
        or "unknown_creator"
    )

    post_id = str(
        info.get("id")
        or "unknown_post"
    )

    description = (
        info.get("description")
        or info.get("title")
        or ""
    )

    upload_date = (
        info.get("upload_date")
        or ""
    )

    formats = info.get(
        "formats",
        []
    )

    best_video = None

    for fmt in formats:

        if not fmt.get("vcodec") or fmt.get("vcodec") == "none":
            continue

        if best_video is None:
            best_video = fmt
            continue

        current_height = (
            fmt.get("height") or 0
        )

        best_height = (
            best_video.get("height") or 0
        )

        current_bitrate = (
            fmt.get("tbr") or 0
        )

        best_bitrate = (
            best_video.get("tbr") or 0
        )

        if (
            current_height > best_height
            or (
                current_height == best_height
                and current_bitrate > best_bitrate
            )
        ):

            best_video = fmt

    quality = {}

    if best_video:

        quality = {
            "width": best_video.get("width"),
            "height": best_video.get("height"),
            "fps": best_video.get("fps"),
            "video_codec": best_video.get("vcodec"),
            "video_bitrate_kbps": best_video.get("tbr"),
        }

    return {
        "platform": "X",
        "creator": creator,
        "post_id": post_id,
        "post_url": url,
        "description": description,
        "title": info.get("title"),
        "upload_date": upload_date,
        "uploader_url": info.get("uploader_url"),
        "webpage_url": info.get("webpage_url") or url,
        "media_type": "video",
        "quality": quality,
    }


def extract_post_metadata(url: str):

    try:

        return extract_video_metadata(
            url
        )

    except yt_dlp.utils.DownloadError as error:

        error_text = str(error)

        if (
            "No video could be found in this tweet"
            not in error_text
        ):

            raise

        html = get_x_page(
            url
        )

        metadata = extract_x_fallback_metadata(
            url,
            html
        )

        image_urls = re.findall(
            r'https://pbs\.twimg\.com/media/[^"\\?]+',
            html
        )

        image_urls = list(
            dict.fromkeys(
                image_urls
            )
        )

        if image_urls:

            metadata["media_type"] = "photo"

        else:

            metadata["media_type"] = "text"

        metadata["image_urls"] = [
            image_url.replace(
                r"\u0026",
                "&"
            )
            for image_url in image_urls
        ]

        return metadata


def download_video_post(
    url: str,
    metadata=None
):

    if metadata is None:

        metadata = extract_video_metadata(
            url
        )

    creator = safe_name(
        metadata.get("creator")
        or "unknown_creator"
    )

    post_id = str(
        metadata.get("post_id")
        or "unknown_post"
    )

    upload_date = (
        metadata.get("upload_date")
        or ""
    )

    post_folder = create_post_folder(
        creator,
        upload_date,
        post_id
    )

    output_template = str(
        post_folder / "media.%(ext)s"
    )

    download_options = {
    "outtmpl": output_template,
    "noplaylist": True,
    "quiet": False,
    "no_warnings": False,
    "cookiesfrombrowser": ("firefox",),
    "format": "bestvideo*+bestaudio/best",
    "merge_output_format": "mp4",
    }

    print(
        f"\nCreator: {creator}"
    )

    print(
        f"Post ID: {post_id}"
    )

    print(
        f"Saving to: {post_folder}"
    )

    with yt_dlp.YoutubeDL(
        download_options
    ) as ydl:

        ydl.download(
            [url]
        )

    save_metadata(
        post_folder,
        metadata
    )

    metadata["folder_path"] = str(
        post_folder
    )

    return metadata


def download_x_fallback(
    url: str,
    metadata=None
):

    if metadata is None:

        metadata = extract_post_metadata(
            url
        )

    print(
        "\nTrying X fallback:"
    )

    print(url)

    creator = metadata.get(
        "creator",
        "unknown_creator"
    )

    post_id = metadata.get(
        "post_id",
        "unknown_post"
    )

    upload_date = metadata.get(
        "upload_date",
        ""
    )

    post_folder = create_post_folder(
        creator,
        upload_date,
        post_id
    )

    image_urls = metadata.get(
        "image_urls",
        []
    )

    if image_urls:

        downloaded_files = []

        for index, image_url in enumerate(
            image_urls,
            start=1
        ):

            image_url = (
                image_url
                + "?format=jpg&name=orig"
            )

            filename = (
                f"image_{index}.jpg"
            )

            output_path = (
                post_folder / filename
            )

            download_image(
                image_url,
                output_path
            )

            downloaded_files.append(
                filename
            )

        metadata["files"] = (
            downloaded_files
        )

        metadata["media_type"] = "photo"

        save_metadata(
            post_folder,
            metadata
        )

        metadata["folder_path"] = str(
            post_folder
        )

        print(
            f"Downloaded {len(downloaded_files)} image(s)."
        )

        return metadata

    metadata["files"] = []

    metadata["media_type"] = "text"

    save_metadata(
        post_folder,
        metadata
    )

    metadata["folder_path"] = str(
        post_folder
    )

    print(
        "No media found."
    )

    print(
        "Saved as text-only post."
    )

    return metadata


def download_post(
    url: str,
    metadata=None
):

    if metadata is None:

        metadata = extract_post_metadata(
            url
        )

    media_type = metadata.get(
        "media_type"
    )

    if media_type == "video":

        return download_video_post(
            url,
            metadata
        )

    return download_x_fallback(
        url,
        metadata
    )


if __name__ == "__main__":

    url = input(
        "Enter X post URL: "
    ).strip()

    if not url:

        print(
            "No URL provided."
        )

        raise SystemExit(1)

    metadata = extract_post_metadata(
        url
    )

    print(
        json.dumps(
            metadata,
            indent=4,
            ensure_ascii=False
        )
    )

    choice = input(
        "\nDownload this post? (y/n): "
    ).strip().lower()

    if choice == "y":

        download_post(
            url,
            metadata
        )