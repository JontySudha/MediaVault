from pathlib import Path
import html
from urllib.parse import quote
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import re
def escape_html(value):

    if value is None:
        return ""

    value = html.unescape(
        str(value)
    )

    return (
        value
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )
    
def clean_description(value):
    if not value:
        return ""

    text = str(value)

    # Normalize Windows/Unix line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove leading/trailing whitespace from every line
    lines = [
        line.strip()
        for line in text.split("\n")
    ]

    # Remove empty lines
    lines = [
        line
        for line in lines
        if line
    ]

    # Rebuild with a single newline between meaningful lines
    return "\n".join(lines)
MENTION_PATTERN = re.compile(
    r"(?<![\w@])@([A-Za-z0-9_]{1,15})(?![\w])"
)


def render_mentions(text, creators):

    if not text:
        return ""

    creator_map = {}

    for creator in creators:

        username = (
            creator.get("username")
            or ""
        ).strip().lstrip("@").lower()

        if username:
            creator_map[username] = creator

    parts = []
    last_end = 0

    for match in MENTION_PATTERN.finditer(
        str(text)
    ):

        parts.append(
            escape_html(
                str(text)[last_end:match.start()]
            )
        )

        username = match.group(1)
        username_lower = username.lower()

        creator = creator_map.get(
            username_lower
        )

        x_url = (
            f"https://x.com/{quote(username)}"
        )

        local_button = ""

        if creator:

            creator_id = creator["id"]

            local_button = f"""
                <a
                    class="mention-option"
                    href="/creator/{creator_id}"
                >
                    Open Local Profile
                </a>
            """

        parts.append(
            f"""
            <span class="mention-wrapper">

                <a
                    class="mention-link"
                    href="{x_url}"
                    target="_blank"
                    rel="noopener noreferrer"
                >
                    @{escape_html(username)}
                </a>

                <span class="mention-menu">

                    <a
                        class="mention-option"
                        href="{x_url}"
                        target="_blank"
                        rel="noopener noreferrer"
                    >
                        Open X Profile
                    </a>

                    {local_button}

                </span>

            </span>
            """
        )

        last_end = match.end()

    parts.append(
        escape_html(
            str(text)[last_end:]
        )
    )

    return "".join(parts)

from app.database import (
    init_database,
    add_creator,
    get_creators,
    get_posts,
    get_creator,
    get_creator_posts,
    get_post,
    get_media,
    add_post,
    add_media,
    update_creator_name,
    delete_post,
    delete_creator,
    get_post_by_id,
)

from app.creator_downloader import (
    get_creator_posts as discover_creator_posts,
    get_older_creator_posts,
)

from app.sync import sync_creator

from app.scheduler import (
    start_scheduler,
    stop_scheduler,
)


app = FastAPI(
    title="MediaVault",
    version="0.1.0",
)


GALLERY_DIR = Path("gallery")


app.mount(
    "/gallery",
    StaticFiles(directory=str(GALLERY_DIR)),
    name="gallery",
)


@app.on_event("startup")
def startup():

    init_database()

    start_scheduler()


@app.on_event("shutdown")
def shutdown():

    stop_scheduler()



def local_file_url(file_path):

    if not file_path:
        return None

    path = Path(file_path)

    try:

        relative = path.relative_to(
            GALLERY_DIR
        )

    except ValueError:

        try:

            relative = path.resolve().relative_to(
                GALLERY_DIR.resolve()
            )

        except ValueError:

            return None

    relative_url = str(
        relative
    ).replace("\\", "/")

    return (
        "/gallery/"
        + quote(
            relative_url,
            safe="/"
        )
    )


def get_post_files(post):

    folder_path = post.get(
        "folder_path"
    )

    if not folder_path:
        return []

    folder = Path(
        folder_path
    )

    if not folder.exists():
        return []

    files = []

    for file in folder.iterdir():

        if not file.is_file():
            continue

        if file.name in {
            "metadata.json",
            "description.txt",
        }:
            continue

        files.append(file)

    return files

def get_post_quality(post):

    folder_path = post.get(
        "folder_path"
    )

    if not folder_path:
        return ""

    metadata_file = (
        Path(folder_path)
        / "metadata.json"
    )

    if not metadata_file.exists():
        return ""

    try:

        import json

        with open(
            metadata_file,
            "r",
            encoding="utf-8"
        ) as file:

            metadata = json.load(file)

    except Exception:

        return ""

    quality = metadata.get(
        "quality",
        {}
    )

    height = quality.get(
        "height"
    )

    width = quality.get(
        "width"
    )

    fps = quality.get(
        "fps"
    )

    codec = quality.get(
        "video_codec"
    )

    if not height:
        return ""

    details = []

    if width and height:

        details.append(
            f"{width}×{height}"
        )

    if fps:

        details.append(
            f"{fps:g} FPS"
        )

    if codec:

        details.append(
            codec
        )

    return (
        '<div class="quality-info">'
        + " • ".join(details)
        + "</div>"
    )

def build_media_html(post):

    files = get_post_files(
        post
    )

    if not files:

        return """
        <div class="text-post">
            <div class="text-icon">𝕏</div>
            <div class="text-label">
                Text / No media
            </div>
        </div>
        """

    html = ""

    for file in files:

        file_url = local_file_url(
            str(file)
        )

        if not file_url:
            continue

        suffix = file.suffix.lower()

        if suffix in {
            ".mp4",
            ".webm",
            ".mov",
            ".mkv",
        }:

            html += f"""
            <div class="media-wrapper">
                <video
                    class="post-video"
                    controls
                    playsinline
                    preload="metadata"
                >
                    <source
                        src="{file_url}"
                    >
                    Your browser does not support
                    video playback.
                </video>
            </div>
            """

        elif suffix in {
            ".jpg",
            ".jpeg",
            ".png",
            ".webp",
            ".gif",
        }:

            html += f"""
            <div class="media-wrapper">
                <img
                    class="post-image"
                    src="{file_url}"
                    loading="lazy"
                >
            </div>
            """

        elif suffix in {
            ".mp3",
            ".m4a",
            ".wav",
        }:

            html += f"""
            <div class="audio-wrapper">
                <audio controls>
                    <source src="{file_url}">
                </audio>
            </div>
            """

    if not html:

        return """
        <div class="text-post">
            <div class="text-icon">𝕏</div>
            <div class="text-label">
                Text / No media
            </div>
        </div>
        """

    return html


def creator_display_name(creator):

    return (
        creator.get("display_name")
        or creator.get("username")
        or creator.get("profile_url")
        or "Unknown Creator"
    )
def format_post_date(value):

    if not value:
        return ""

    value = str(value)

    if len(value) == 8 and value.isdigit():

        return (
            f"{value[:4]}-"
            f"{value[4:6]}-"
            f"{value[6:8]}"
        )

    return value

def render_page(
    title,
    content,
    back_button=False
):

    back_html = ""

    if back_button:

        back_html = """
        <a class="back-button" href="/">
            ← All Creators
        </a>
        """

    return f"""
    <!DOCTYPE html>

    <html>

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width,
                     initial-scale=1.0"
        >

        <title>
            {escape_html(title)}
            - MediaVault
        </title>

        <style>

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                background: #000;
                color: #e7e9ea;
                font-family:
                    Arial,
                    Helvetica,
                    sans-serif;
            }}

            a {{
                color: inherit;
                text-decoration: none;
            }}

            .app {{
                width: 100%;
                max-width: 1100px;
                margin: auto;
            }}
            
            .quality-info {{
                color: #71767b;
                font-size: 13px;
                margin-bottom: 8px;
            }}
            
            .header {{
                position: sticky;
                top: 0;
                z-index: 10;

                background:
                    rgba(0, 0, 0, 0.92);

                backdrop-filter:
                    blur(10px);

                border-bottom:
                    1px solid #2f3336;

                padding: 18px 24px;
            }}
            
            .creator-actions {{
                display: flex;
                gap: 10px;
                flex-wrap: wrap;
                margin-top: 10px;
            }}

            .gallery-button {{
                display: inline-flex;

                align-items: center;
                justify-content: center;

                padding: 12px 22px;

                border-radius: 999px;

                background: #1d9bf0;

                color: white;

                font-weight: 700;
            }}

            .gallery-button:hover {{
                background: #1a8cd8;
            }}

            .older-button {{
                background: #16181c;
                color: #e7e9ea;
                border: 1px solid #2f3336;
            }}

            .older-button:hover {{
                background: #272c30;
            }}
            
            .logo {{
                font-size: 26px;
                font-weight: 800;
                color: inherit;
                text-decoration: none;
            }}

            .header-row {{
                display: flex;
                align-items: center;
                gap: 16px;
            }}


            .title {{
                font-size: 20px;
                font-weight: 700;
            }}

            .content {{
                padding: 24px;
            }}

            .back-button {{
                display: inline-block;
                margin-bottom: 20px;
                color: #1d9bf0;
                font-weight: 600;
            }}

            .add-box {{
                border:
                    1px solid #2f3336;

                border-radius: 18px;

                padding: 20px;

                margin-bottom: 28px;
            }}

            .add-box h2 {{
                margin-top: 0;
            }}

            .add-form {{
                display: flex;
                gap: 10px;
            }}

            .url-input {{
                flex: 1;

                background: #16181c;

                border:
                    1px solid #2f3336;

                border-radius: 999px;

                padding: 14px 18px;

                color: white;

                font-size: 15px;

                outline: none;
            }}

            .url-input:focus {{
                border-color: #1d9bf0;
            }}

            button {{
                border: none;

                border-radius: 999px;

                padding: 12px 22px;

                background: #1d9bf0;

                color: white;

                font-weight: 700;

                cursor: pointer;
            }}

            button:hover {{
                background: #1a8cd8;
            }}

            .creators-grid {{
                display: grid;

                grid-template-columns:
                    repeat(
                        auto-fill,
                        minmax(260px, 1fr)
                    );

                gap: 16px;
            }}

            .creator-card {{
                border:
                    1px solid #2f3336;

                border-radius: 18px;

                padding: 20px;

                background: #000;

                transition:
                    background 0.2s,
                    transform 0.2s;
            }}

            .creator-card:hover {{
                background: #08090a;
                transform: translateY(-2px);
            }}

            .creator-avatar {{
                width: 64px;
                height: 64px;

                border-radius: 50%;

                background: #1d9bf0;

                display: flex;
                align-items: center;
                justify-content: center;

                font-size: 28px;
                font-weight: 800;

                margin-bottom: 15px;
            }}

            .creator-name {{
                font-size: 20px;
                font-weight: 800;
                margin-bottom: 5px;
            }}

            .creator-username {{
                color: #71767b;
                margin-bottom: 16px;
            }}

            .creator-button {{
                display: inline-block;

                background: #eff3f4;
                color: #0f1419;

                border-radius: 999px;

                padding: 9px 18px;

                font-weight: 700;
            }}

            .creator-page-header {{
                border-bottom:
                    1px solid #2f3336;

                padding-bottom: 20px;

                margin-bottom: 20px;
            }}

            .creator-page-name {{
                font-size: 30px;
                font-weight: 800;
            }}

            .creator-page-url {{
                color: #71767b;
                margin-top: 5px;
            }}

            .post-card {{
                border:
                    1px solid #2f3336;

                border-radius: 18px;

                padding: 18px;

                margin-bottom: 18px;

                background: #000;
            }}

            .post-header {{
                display: flex;
                align-items: center;
                justify-content: space-between;

                margin-bottom: 12px;
            }}

            .post-creator {{
                font-weight: 800;
            }}

            .post-date {{
                color: #71767b;
                font-size: 13px;
            }}

            .description {{
                white-space: pre-wrap;

                line-height: 1.5;

                margin-bottom: 15px;

                color: #e7e9ea;
            }}

            .media-wrapper {{
                overflow: hidden;

                border-radius: 16px;

                background: #111;

                margin-top: 10px;
            }}

            .post-video {{
                display: block;

                width: 100%;

                max-height: 650px;

                background: #000;
            }}

            .post-image {{
                display: block;

                width: 100%;

                max-height: 700px;

                object-fit: contain;

                background: #000;
            }}

            .audio-wrapper {{
                padding: 15px;

                background: #16181c;

                border-radius: 14px;
            }}

            .audio-wrapper audio {{
                width: 100%;
            }}

            .open-post {{
                display: inline-block;

                margin-top: 15px;

                color: #1d9bf0;

                font-weight: 600;
            }}

            .text-post {{
                border:
                    1px solid #2f3336;

                border-radius: 16px;

                min-height: 130px;

                display: flex;

                align-items: center;

                justify-content: center;

                flex-direction: column;

                background: #08090a;
            }}

            .text-icon {{
                font-size: 40px;
                margin-bottom: 8px;
            }}

            .text-label {{
                color: #71767b;
            }}

            .empty {{
                text-align: center;

                padding: 80px 20px;

                color: #71767b;
            }}

            .sync-button {{
                margin-top: 10px;
                background: #eff3f4;
                color: #0f1419;
            }}
            
            .gallery-page-header {{
                margin-bottom: 25px;
            }}

            .gallery-page-header h1 {{
                margin-bottom: 5px;
            }}

            .full-gallery {{
                display: grid;

                grid-template-columns:
                    repeat(
                        auto-fill,
                        minmax(260px, 1fr)
                    );

                gap: 14px;
            }}

            .full-gallery-item {{
                display: flex;

                align-items: center;
                justify-content: center;

                overflow: hidden;

                border:
                    1px solid #2f3336;

                border-radius: 16px;

                background: #08090a;

                min-height: 260px;
            }}

            .full-gallery-item img {{
                display: block;

                width: 100%;
                height: 100%;

                max-height: 500px;

                object-fit: contain;

                background: #000;
            }}

            .full-gallery-item video {{
                display: block;

                width: 100%;
                height: 100%;

                max-height: 500px;

                background: #000;
            }}

            .audio-gallery-item {{
                padding: 25px;
            }}

            .audio-gallery-item audio {{
                width: 100%;
            }}

            @media (max-width: 650px) {{

                .full-gallery {{
                    grid-template-columns:
                        repeat(2, 1fr);

                    gap: 8px;
                }}

                .full-gallery-item {{
                    min-height: 170px;
                }}

            }}

            @media (max-width: 650px) {{

                .content {{
                    padding: 14px;
                }}

                .header {{
                    padding: 15px;
                }}

                .add-form {{
                    flex-direction: column;
                }}

                .creators-grid {{
                    grid-template-columns: 1fr;
                }}

            }}

            .mention-wrapper {{
                position: relative;
                display: inline-block;
            }}

            .mention-link {{
                color: #1d9bf0;
                text-decoration: none;
                font-weight: 600;
            }}

            .mention-link:hover {{
                text-decoration: underline;
            }}

            .mention-menu {{
    display: none;

    position: absolute;

    left: 0;
    top: calc(100% + 4px);

    width: max-content;
    min-width: 145px;
    max-width: 190px;

    padding: 4px;

    background: #16181c;

    border:
        1px solid #2f3336;

    border-radius: 8px;

    box-shadow:
        0 6px 18px rgba(0, 0, 0, 0.35);

    z-index: 100;
}}

            .mention-wrapper:hover .mention-menu {{
                display: block;
            }}

            .mention-option {{
    display: block;

    padding: 6px 9px;

    border-radius: 6px;

    color: #ffffff;

    font-size: 13px;

    font-weight: 5;

    line-height: 1.2;

    white-space: nowrap;
}}

.mention-option:hover {{
    background: #272c30;

    text-decoration: none;
}}
            
        </style>

    </head>

    <body>

        <div class="app">

            <header class="header">

                <div class="header-row">

                    <a
                        class="logo"
                        href="/"
                    >
                        𝕏
                    </a>

                    <div class="title">
                        MediaVault
                    </div>

                </div>

            </header>

            <main class="content">

                {back_html}

                {content}

            </main>

        </div>

    </body>

    </html>
    """


@app.get(
    "/",
    response_class=HTMLResponse
)
def home():

    creators = get_creators()

    creator_cards = ""

    for creator in creators:

        name = creator_display_name(
            creator
        )

        username = (
            creator.get("username")
            or ""
        )

        creator_cards += f"""
        <a
            href="/creator/{creator['id']}"
            class="creator-card"
        >

            <div class="creator-avatar">
                {escape_html(name[:1].upper())}
            </div>

            <div class="creator-name">
                {escape_html(name)}
            </div>

            <div class="creator-username">
                @{escape_html(username)}
            </div>

            <span class="creator-button">
                Open Creator
            </span>

        </a>
        """

    if not creator_cards:

        creator_cards = """
        <div class="empty">

            <h2>
                No creators yet
            </h2>

            <p>
                Add an X creator above
                to start building your archive.
            </p>

        </div>
        """

    content = f"""

        <div class="add-box">

            <h2>
                Add Creator
            </h2>

            <form
                class="add-form"
                method="post"
                action="/creators/add"
            >

                <input
                    class="url-input"
                    type="url"
                    name="profile_url"
                    placeholder="https://x.com/username"
                    required
                >

                <button type="submit">
                    Add Creator
                </button>

            </form>

        </div>

        <div style="margin-bottom: 28px;">

        <a
            href="/posts"
            class="creator-button"
        >
            View All Posts →
        </a>

        </div>

        <h2>
            Your Creators
        </h2>

        <div class="creators-grid">

            {creator_cards}

        </div>

    """

    return render_page(
        "Home",
        content
    )
@app.get(
    "/posts",
    response_class=HTMLResponse
)
def all_posts():

    posts = get_posts()

    post_cards = ""

    for post in posts:

        creator_name = (
            post.get("display_name")
            or post.get("username")
            or "Unknown Creator"
        )

        description = clean_description(
    post.get("description") or ""
)

        description_html = render_mentions(
            description,
            get_creators()
        )

        created_at = format_post_date(
            post.get("created_at")
            or post.get("downloaded_at")
            or ""
        )

        media_html = build_media_html(
            post
        )

        post_cards += f"""
        <article class="post-card">

            <div class="post-header">

                <div class="post-creator">
                    {escape_html(creator_name)}
                </div>

                <div class="post-date">
                    {escape_html(created_at)}
                </div>

            </div>

            <div class="description">
                {description_html}
            </div>

            {media_html}

            <a
                class="open-post"
                href="{escape_html(post['post_url'])}"
                target="_blank"
            >
                Open Original Post →
            </a>

        </article>
        """

    if not post_cards:

        post_cards = """
        <div class="empty">

            <h2>
                No posts yet
            </h2>

            <p>
                Add a creator and sync posts
                to build your MediaVault.
            </p>

        </div>
        """

    content = f"""

        <div class="creator-page-header">

            <div class="creator-page-name">
                All Posts
            </div>

            <div class="creator-page-url">
                Posts from all your creators
            </div>

        </div>

        {post_cards}

    """

    return render_page(
        "All Posts",
        content,
        back_button=True
    )

@app.get(
    "/creator/{creator_id}",
    response_class=HTMLResponse
)
def creator_page(
    creator_id: int
):

    creator = get_creator(
        creator_id
    )

    if not creator:

        return HTMLResponse(
            "Creator not found.",
            status_code=404
        )

    posts = get_creator_posts(
        creator_id
    )

    creators = get_creators()

    name = creator_display_name(
        creator
    )

    username = (
        creator.get("username")
        or ""
    )

    post_cards = ""

    for post in posts:

        description = clean_description(
    post.get("description") or ""
)

        description_html = render_mentions(
            description,
            creators
        )

        created_at = format_post_date(
            post.get("created_at")
            or post.get("downloaded_at")
            or ""
        )

        media_html = build_media_html(
            post
        )

        quality_html = get_post_quality(
            post
        )

        post_cards += f"""

        <article
            class="post-card"
            id="post-{post['id']}"
        >

            <div class="post-header">

                <div class="post-creator">
                    {escape_html(name)}
                </div>

                <div class="post-date">
                    {escape_html(created_at)}
                </div>

            </div>

            <div class="description">
                {description_html}
            </div>

            {quality_html}
            
            {media_html}

            <a
                class="open-post"
                href="{escape_html(post['post_url'])}"
                target="_blank"
            >
                Open Original Post →
            </a>

<form
    method="post"
    action="/posts/{post['id']}/delete"
    onsubmit="return confirm('Delete this post?');"
    style="margin-top: 10px;"
>

    <button
        type="submit"
    >
        Delete Post
    </button>

</form>

        </article>

        """

    if not post_cards:

        post_cards = """
        <div class="empty">

            <h2>
                No posts downloaded yet
            </h2>

            <p>
                Run Sync to download this
                creator's posts.
            </p>

        </div>
        """

    content = f"""

        <div class="creator-page-header">

            <div class="creator-page-name">
                {escape_html(name)}
            </div>

            <div class="creator-page-url">
                @{escape_html(username)}
            </div>

            <div class="creator-actions">

    <form
        method="post"
        action="/creators/{creator_id}/sync"
    >

        <button
            class="sync-button"
            type="submit"
        >
            Sync New Posts
        </button>

    </form>


    <form
        method="post"
        action="/creators/{creator_id}/import-older"
    >

        <button
            class="older-button"
            type="submit"
        >
            Import Older Posts
        </button>

    </form>

   <a
    class="gallery-button"
    href="/creator/{creator_id}/gallery"
    onclick="saveCurrentPost()"
>
    Open Gallery
</a>

    <form
        method="post"
        action="/creators/{creator_id}/delete"
        onsubmit="return confirm('Delete this creator and all downloaded posts and files?');"
    >

        <button
            type="submit"
        >
            Delete Creator
        </button>

    </form>

</div>

        </div>

         {post_cards}

        <script>

            const creatorId = "{creator_id}";

            const postElements =
                document.querySelectorAll(".post-card");


            function saveCurrentPost() {{

                let closestPost = null;
                let closestDistance = Infinity;

                postElements.forEach(function(post) {{

                    const rect =
                        post.getBoundingClientRect();

                    const distance =
                        Math.abs(rect.top);

                    if (distance < closestDistance) {{

                        closestDistance = distance;
                        closestPost = post;

                    }}

                }});

                if (closestPost) {{

                    sessionStorage.setItem(
                        "creator_post_" + creatorId,
                        closestPost.id
                    );

                }}

            }}


            window.addEventListener(
                "scroll",
                saveCurrentPost
            );


            window.addEventListener(
                "load",
                function() {{

                    const savedPostId =
                        sessionStorage.getItem(
                            "creator_post_" + creatorId
                        );

                    if (!savedPostId) {{
                        return;
                    }}

                    const post =
                        document.getElementById(
                            savedPostId
                        );

                    if (post) {{

                        setTimeout(
                            function() {{

                                post.scrollIntoView({{
                                    behavior: "instant",
                                    block: "start"
                                }});

                            }},
                            100
                        );

                    }}

                }}
            );

        </script>

    """

    return render_page(
        name,
        content,
        back_button=True
    )


@app.post(
    "/creators/add"
)
def create_creator(
    profile_url: str = Form(...)
):

    profile_url = (
        profile_url
        .strip()
        .rstrip("/")
    )

    username = (
        profile_url
        .split("?")[0]
        .rstrip("/")
        .split("/")[-1]
    )

    creator_id = add_creator(
        platform="X",
        username=username,
        profile_url=profile_url,
        display_name=username,
    )

    try:

        discovered = discover_creator_posts(
            profile_url
        )

        if discovered:

            first_post = discovered[0]

            from app.downloader import (
                extract_post_metadata
            )

            try:

                metadata = extract_post_metadata(
                    first_post["url"]
                )

                creator_name = metadata.get(
                    "creator"
                )

                if creator_name:

                    from app.database import (
                        update_creator_name
                    )

                    update_creator_name(
                        creator_id,
                        creator_name,
                        metadata.get(
                            "username"
                        )
                        or username
                    )

            except Exception:
                pass

    except Exception:
        pass

    return RedirectResponse(
        "/",
        status_code=303
    )


@app.post(
    "/creators/{creator_id}/sync"
)
def sync_creator_route(
    creator_id: int
):

    sync_creator(
        creator_id
    )

    return RedirectResponse(
        f"/creator/{creator_id}",
        status_code=303
    )

@app.post(
    "/creators/{creator_id}/import-older"
)
def import_older_posts(
    creator_id: int
):

    creator = get_creator(
        creator_id
    )

    if not creator:

        return HTMLResponse(
            "Creator not found.",
            status_code=404
        )

    profile_url = creator[
        "profile_url"
    ]

    print(
        "\n[Older Import] Starting..."
    )

    older_posts = get_older_creator_posts(
        profile_url,
        limit=None
    )

    BATCH_SIZE = 15

    total_posts = len(
        older_posts
    )

    print(
        f"[Older Import] Total posts found: "
        f"{total_posts}"
    )

    imported = 0
    skipped = 0
    errors = 0

    from app.sync import (
        download_gallery_media,
        save_post_metadata,
        record_media_files,
    )

    for batch_start in range(
        0,
        total_posts,
        BATCH_SIZE
    ):

        batch = older_posts[
            batch_start:
            batch_start + BATCH_SIZE
        ]

        batch_number = (
            batch_start // BATCH_SIZE
        ) + 1

        print(
            f"\n[Older Import] "
            f"Batch {batch_number} | "
            f"{len(batch)} posts"
        )

        for older_post in batch:

            discovered_id = str(
                older_post["id"]
            )

            try:

                existing = get_post(
                    creator_id,
                    discovered_id
                )

                if existing:

                    skipped += 1

                    print(
                        f"[Older Import] "
                        f"Skipped {discovered_id}"
                    )

                    continue

                creator_name = (
                    older_post.get(
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
                    older_post.get(
                        "username"
                    )
                    or creator.get(
                        "username"
                    )
                )

                update_creator_name(
                    creator_id,
                    creator_name,
                    username
                )

                upload_date = (
                    older_post.get(
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
                    exist_ok=True
                )

                print(
                    f"\n[Older Import] "
                    f"Downloading {discovered_id}"
                )

                downloaded_files = (
                    download_gallery_media(
                        older_post,
                        post_folder
                    )
                )

                save_post_metadata(
                    post_folder,
                    older_post
                )

                database_post_id = add_post(
                    creator_id=creator_id,
                    platform_post_id=discovered_id,
                    post_url=older_post[
                        "url"
                    ],
                    description=(
                        older_post.get(
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
                    post_folder
                )

                imported += 1

                print(
                    f"[Older Import] "
                    f"Imported {discovered_id} "
                    f"({len(downloaded_files)} files)"
                )

            except Exception as error:

                errors += 1

                print(
                    f"[Older Import] Error "
                    f"{discovered_id}: {error}"
                )

    print(
        f"\n[Older Import] Complete | "
        f"imported={imported} | "
        f"skipped={skipped} | "
        f"errors={errors}"
    )

    return RedirectResponse(
        f"/creator/{creator_id}",
        status_code=303
    )

@app.get(
    "/creators/check"
)
def check_creator(
    profile_url: str
):

    posts = discover_creator_posts(
        profile_url
    )

    return {
        "profile_url": profile_url,
        "post_count": len(posts),
        "posts": posts,
    }
@app.post(
    "/posts/{post_id}/delete"
)
def delete_post_route(
    post_id: int
):

    post = get_post_by_id(
        post_id
    )

    if not post:
        return HTMLResponse(
            "Post not found.",
            status_code=404
        )

    creator_id = post["creator_id"]

    folder_path = post.get(
        "folder_path"
    )

    if folder_path:

        folder = Path(
            folder_path
        )

        if folder.exists() and folder.is_dir():

            import shutil

            shutil.rmtree(
                folder
            )

    delete_post(
        post_id
    )

    return RedirectResponse(
        f"/creator/{creator_id}",
        status_code=303
    )

@app.post(
    "/creators/{creator_id}/delete"
)
def delete_creator_route(
    creator_id: int
):

    creator = get_creator(
        creator_id
    )

    if not creator:

        return HTMLResponse(
            "Creator not found.",
            status_code=404
        )

    creator_name = creator_display_name(
        creator
    )

    creator_folder = (
        GALLERY_DIR / creator_name
    )

    if (
        creator_folder.exists()
        and creator_folder.is_dir()
    ):

        import shutil

        shutil.rmtree(
            creator_folder
        )

    delete_creator(
        creator_id
    )

    return RedirectResponse(
        "/",
        status_code=303
    )
@app.get(
    "/creator/{creator_id}/gallery",
    response_class=HTMLResponse
)
def creator_gallery(
    creator_id: int
):

    creator = get_creator(
        creator_id
    )

    if not creator:

        return HTMLResponse(
            "Creator not found.",
            status_code=404
        )

    posts = get_creator_posts(
        creator_id
    )

    name = creator_display_name(
        creator
    )

    username = (
        creator.get("username")
        or ""
    )

    gallery_items = ""

    for post in posts:

        files = get_post_files(
            post
        )

        for file in files:

            file_url = local_file_url(
                str(file)
            )

            if not file_url:
                continue

            suffix = file.suffix.lower()

            post_id = post["id"]

            if suffix in {
                ".jpg",
                ".jpeg",
                ".png",
                ".webp",
                ".gif",
            }:

                gallery_items += f"""
                <a
                    class="full-gallery-item"
                    href="{file_url}"
                    target="_blank"
                    data-post-id="{post_id}"
                >

                    <img
                        src="{file_url}"
                        loading="lazy"
                        alt=""
                    >

                </a>
                """

            elif suffix in {
                ".mp4",
                ".webm",
                ".mov",
                ".mkv",
            }:

                gallery_items += f"""
                <div
                    class="full-gallery-item"
                    data-post-id="{post_id}"
                >

                    <video
                        controls
                        preload="metadata"
                    >

                        <source
                            src="{file_url}"
                        >

                    </video>

                </div>
                """

            elif suffix in {
                ".mp3",
                ".m4a",
                ".wav",
            }:

                gallery_items += f"""
                <div
                    class="full-gallery-item audio-gallery-item"
                    data-post-id="{post_id}"
                >

                    <audio controls>

                        <source
                            src="{file_url}"
                        >

                    </audio>

                </div>
                """

    if not gallery_items:

        gallery_items = """
        <div class="empty">

            <h2>
                No media yet
            </h2>

        </div>
        """
    
    content = f"""

        <div class="gallery-page-header">

            <a
                class="back-button"
                href="/creator/{creator_id}"
            >
                ← Back to {escape_html(name)}
            </a>

            <h1>
                {escape_html(name)} Gallery
            </h1>

            <div class="creator-page-url">
                @{escape_html(username)}
            </div>

        </div>

        <div class="full-gallery">

            {gallery_items}

        </div>

    """

    return render_page(
        f"{name} Gallery",
        content,
        back_button=False
    )
