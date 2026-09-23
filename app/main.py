from pathlib import Path
import html
import json
import re
import shutil
import sqlite3
import time
from urllib.parse import quote, urlparse, urljoin

import requests
from html.parser import HTMLParser
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import (
    init_database, add_creator, get_creators, get_creator, get_posts,
    get_creator_posts, add_post, delete_post, delete_creator,
    update_creator_name, update_creator_profile_description,
    update_creator_profile_photo, update_creator_profile_links,
    get_creator_profile_links, is_post_deleted,
)
from app.creator_downloader import (
    get_creator_posts as discover_creator_posts,
    iter_older_creator_posts,
)
from app.sync import (
    sync_creator, download_gallery_media, save_post_metadata,
    record_media_files, remove_incomplete_downloads,
)
from app.scheduler import start_scheduler, stop_scheduler
from app.task_control import (
    request_cancel, is_cancelled, is_task_running,
    start_task, finish_task, clear_cancel,
)


DATABASE_PATH = Path("database") / "media.db"
GALLERY_DIR = Path("gallery")
GALLERY_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="MediaVault", version="0.1.0")
app.mount("/gallery", StaticFiles(directory=str(GALLERY_DIR)), name="gallery")


# ============================================================
# HELPERS
# ============================================================

def escape_html(value):
    return "" if value is None else html.escape(str(value), quote=True)


def render_description(text):
    if not text:
        return ""

    text = escape_html(str(text).strip())

    def url_replace(match):
        url = match.group(1).rstrip(".,!?;:")
        return (
            f'<a class="description-link" href="{escape_html(url)}" '
            'target="_blank" rel="noopener noreferrer">'
            f'{escape_html(url)}</a>'
        )

    text = re.sub(r'(?<!["=])(https?://[^\s<]+)', url_replace, text)

    def mention_replace(match):
        username = match.group(1)
        return (
            f'<a class="mention-link" href="https://x.com/{quote(username)}" '
            'target="_blank" rel="noopener noreferrer">'
            f'@{escape_html(username)}</a>'
        )

    text = re.sub(r"(?<![\w])@([A-Za-z0-9_]{1,30})", mention_replace, text)
    return text.replace("\n", "<br>")


def safe_name(value):
    value = re.sub(r'[<>:"/\\|?*]', "_", str(value or "unknown_creator"))
    return value.strip().rstrip(".")[:100] or "unknown_creator"


def local_file_url(path):
    try:
        relative = Path(path).relative_to(GALLERY_DIR)
    except ValueError:
        return ""
    return "/gallery/" + "/".join(quote(part) for part in relative.parts)


def get_post_files(post):
    folder = post.get("folder_path")
    if not folder:
        return []

    folder = Path(folder)
    if not folder.exists():
        return []

    return [
        p for p in sorted(folder.iterdir())
        if p.is_file()
        and p.name not in {"metadata.json", "description.txt"}
        and not p.name.startswith(".downloading_")
    ]


def media_html(post, compact=False):
    files = get_post_files(post)
    items = []
    for path in files:
        url = local_file_url(path)
        if not url:
            continue
        suffix = path.suffix.lower()
        if suffix in {".mp4", ".webm", ".mov", ".mkv"}:
            items.append({"url": url, "type": "video"})
        elif suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
            items.append({"url": url, "type": "image"})
    if not items:
        return '<div class="empty-media">No supported media files found.</div>'
    media_json = escape_html(json.dumps(items, ensure_ascii=False))
    slides = []
    for index, item in enumerate(items):
        if item["type"] == "video":
            media = f'<video class="post-carousel-media" controls preload="metadata" onclick="event.stopPropagation()"><source src="{escape_html(item["url"])}"></video>'
        else:
            media = f'<img class="post-carousel-media" src="{escape_html(item["url"])}" loading="lazy" alt="Media {index + 1}">'
        active = " active" if index == 0 else ""
        slides.append(f'<button type="button" class="post-carousel-slide{active}" onclick="openPostMedia(this.closest(\'.post-carousel\'), {index})">{media}</button>')
    arrows = ""
    if len(items) > 1:
        arrows = '<button type="button" class="carousel-arrow carousel-prev" onclick="changePostMedia(this.closest(\'.post-carousel\'), -1); event.stopPropagation()">‹</button><button type="button" class="carousel-arrow carousel-next" onclick="changePostMedia(this.closest(\'.post-carousel\'), 1); event.stopPropagation()">›</button>'
    dots = ''.join(f'<button type="button" class="carousel-dot{" active" if i == 0 else ""}" onclick="showPostMedia(this.closest(\'.post-carousel\'), {i}); event.stopPropagation()" aria-label="Media {i + 1}"></button>' for i in range(len(items)))
    return f'<div class="post-carousel" data-media="{media_json}" data-index="0"><div class="post-carousel-viewport">{"".join(slides)}</div><div class="post-carousel-counter">1 / {len(items)}</div>{arrows}<div class="carousel-dots">{dots}</div></div>'


def creator_name(creator):
    return creator.get("display_name") or creator.get("username") or "Unknown Creator"


def creator_username(creator):
    """Return the stable X username from profile_url, not the display name."""
    profile_url = str(creator.get("profile_url") or "")
    match = re.search(r"(?:x\.com|twitter\.com)/([^/?#]+)", profile_url, re.IGNORECASE)
    if match:
        return match.group(1).lstrip("@").strip()
    return str(creator.get("username") or "").lstrip("@").strip()


def profile_links_html(creator):
    links = get_creator_profile_links(creator)
    if not links:
        return ""

    items = []

    for item in links:
        if isinstance(item, dict):
            url = item.get("url", "")
            label = item.get("label", "") or (urlparse(url).netloc or url)
        else:
            url = str(item)
            label = urlparse(url).netloc or url

        if not url:
            continue

        if label.startswith("www."):
            label = label[4:]

        items.append(
            f'<a class="profile-link" href="{escape_html(url)}" '
            'target="_blank" rel="noopener noreferrer">'
            f'🔗 {escape_html(label)}</a>'
        )

    return '<div class="profile-links">' + "".join(items) + "</div>" if items else ""


def render_page(title, content):
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape_html(title)} - MediaVault</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#0f1115;color:#e8eaed;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
a{{color:inherit;text-decoration:none}}

.navbar{{position:sticky;top:0;z-index:1000;display:flex;justify-content:space-between;align-items:center;padding:14px 22px;background:rgba(15,17,21,.96);border-bottom:1px solid #292d35;backdrop-filter:blur(10px)}}
.brand{{font-size:20px;font-weight:700}}
.nav-links,.actions{{display:flex;gap:8px;flex-wrap:wrap}}
.nav-button,.button,button{{padding:9px 13px;border:0;border-radius:8px;background:#272c35;color:#fff;cursor:pointer;font-size:14px}}
.primary{{background:#315d9d}}
.danger{{background:#7d2730}}
.inline{{display:inline}}

.container{{width:min(1200px,94%);margin:auto;padding:25px 0 50px}}
.card{{padding:18px}}
.post-card{{width:100%;overflow:hidden}}
.creator-page-header{{display:flex;gap:16px;align-items:center;padding:14px 16px;margin-bottom:14px;background:rgba(23,26,32,.97);backdrop-filter:blur(12px)}}
.media-modal.open{{display:flex}}
.media-modal-content{{max-width:90vw;max-height:82vh;display:flex;align-items:center;justify-content:center}}
.media-modal-content img,.media-modal-content video{{max-width:90vw;max-height:82vh;width:auto;height:auto;object-fit:contain;background:#000;border-radius:8px}}
.media-modal-counter{{position:fixed;top:22px;left:50%;transform:translateX(-50%);padding:6px 10px;border-radius:999px;background:rgba(255,255,255,.12);color:#fff;font-size:14px;z-index:5002}}
.media-modal-arrow{{position:fixed;top:50%;transform:translateY(-50%);width:46px;height:46px;border:0;border-radius:50%;background:rgba(255,255,255,.14);color:#fff;font-size:34px;line-height:1;z-index:5002;cursor:pointer}}
.media-modal-prev{{left:18px}} .media-modal-next{{right:18px}}
.media-modal-dots{{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);display:flex;gap:7px;z-index:5002}}
.media-modal-dot{{width:8px;height:8px;padding:0;border:0;border-radius:50%;background:#777;cursor:pointer}}
.media-modal-dot.active{{background:#fff}}
.gallery-panel{{background:#171a20;border:1px solid #292d35;border-radius:14px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:18px}}

/* Twitter/X-style vertical posts */
.post-grid{{display:flex;flex-direction:column;gap:18px;max-width:760px;margin:0 auto}}

.creator-card{{display:flex;flex-direction:column;gap:12px}}
.creator-name{{font-size:19px;font-weight:700}}
.muted,.creator-username,.creator-page-username,.post-meta{{color:#969eaa}}
.creator-description,.creator-page-description,.post-description{{color:#c9cdd4;line-height:1.5;font-size:14px}}

input[type=url]{{width:100%;padding:11px 12px;border-radius:8px;border:1px solid #343943;background:#111318;color:#fff}}
.form-group{{margin-bottom:12px}}
.empty-state{{text-align:center;padding:60px 20px;color:#8d95a2}}
.section-title{{margin:25px 0 15px}}

.creator-profile-image{{width:72px;height:72px;border-radius:50%;object-fit:cover;flex-shrink:0;background:#20242c}}
.creator-profile-placeholder{{display:flex;align-items:center;justify-content:center;font-size:30px}}

.creator-page-header{{display:flex;gap:16px;align-items:center;padding:14px 16px;margin-bottom:14px;background:rgba(23,26,32,.97);backdrop-filter:blur(12px)}}
.creator-page-info{{min-width:0;flex:1}}
.creator-page-name{{font-size:24px;font-weight:700}}
.creator-header-actions{{display:flex;gap:8px;flex-wrap:wrap;flex-shrink:0}}

.profile-panel{{padding:16px;margin:0 0 18px;background:#171a20;border:1px solid #292d35;border-radius:14px}}
.profile-links{{display:flex;gap:7px;flex-wrap:wrap;margin-top:9px}}
.profile-link{{padding:6px 9px;border-radius:7px;background:#20242c;color:#8db8ff;font-size:13px}}
.description-link,.mention-link{{color:#76a9f7}}

.post-grid.single-post-grid{{max-width:650px}}
.post-grid.multi-post-grid{{max-width:760px}}
.post-carousel{{position:relative;width:100%;background:#0b0d10}}
.post-carousel-viewport{{position:relative;width:100%;overflow:hidden;background:#000}}
.post-carousel-slide{{display:none;width:100%;padding:0;border:0;background:#000;cursor:pointer}}
.post-carousel-slide.active{{display:flex;align-items:center;justify-content:center}}
.post-carousel-media{{display:block;width:100%;max-height:650px;object-fit:contain;background:#000}}
.post-carousel-counter{{position:absolute;right:12px;top:12px;padding:5px 9px;border-radius:999px;background:rgba(0,0,0,.65);color:#fff;font-size:13px;z-index:3}}
.carousel-arrow{{position:absolute;top:50%;transform:translateY(-50%);width:38px;height:38px;border-radius:50%;border:0;background:rgba(0,0,0,.62);color:#fff;font-size:28px;line-height:1;z-index:3}}
.carousel-prev{{left:10px}} .carousel-next{{right:10px}}
.carousel-dots{{display:flex;justify-content:center;gap:6px;padding:9px 0;background:#0b0d10}}
.carousel-dot{{width:7px;height:7px;padding:0;border:0;border-radius:50%;background:#69717e;cursor:pointer}}
.carousel-dot.active{{background:#fff}}
.post-body{{padding:15px}}

/* Media popup */
.media-modal{{display:none;position:fixed;inset:0;z-index:5000;background:rgba(0,0,0,.88);align-items:center;justify-content:center;padding:30px}}
.media-modal.open{{display:flex}}
.media-modal-content{{max-width:95vw;max-height:90vh;display:flex;align-items:center;justify-content:center}}
.media-modal-content img,.media-modal-content video{{max-width:95vw;max-height:90vh;width:auto;height:auto;object-fit:contain;background:#000;border-radius:8px}}
.media-modal-close{{position:fixed;top:18px;right:24px;width:44px;height:44px;border:0;border-radius:50%;background:rgba(255,255,255,.14);color:#fff;font-size:30px;line-height:1;cursor:pointer;z-index:5001}}
.media-modal-close:hover{{background:rgba(255,255,255,.25)}}

.gallery-item{{cursor:pointer}}

.gallery-panel{{padding:15px;margin:18px 0 25px}}
.gallery-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;margin-top:12px}}
.gallery-item{{display:block;width:100%;padding:0;aspect-ratio:1/1;overflow:hidden;border-radius:9px;background:#0b0d10;border:1px solid #292d35;cursor:pointer}}
.gallery-thumb{{width:100%;height:100%;object-fit:cover;display:block}}
.gallery-empty,.empty-media{{padding:25px;color:#777f8c;text-align:center}}

.gallery-page-header{{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:20px}}
.gallery-page-title{{margin:0;font-size:28px}}

@media(max-width:700px){{
    .post-media{{grid-template-columns:repeat(2,minmax(0,1fr))}}
    .creator-page-header{{flex-wrap:wrap}}
    .creator-header-actions{{width:100%}}
    .grid{{grid-template-columns:1fr}}
    .post-grid{{max-width:100%}}
    .gallery-page-header{{align-items:flex-start;flex-direction:column}}
}}
</style>
</head>
<body>
<nav class="navbar">
    <a class="brand" href="/">MediaVault</a>
    <div class="nav-links">
        <a class="nav-button" href="/">Creators</a>
        <a class="nav-button" href="/posts">All Posts</a>
    </div>
</nav>
<main class="container">{content}</main>

<div id="mediaModal" class="media-modal" onclick="closeMediaModal(event)">
<button type="button" class="media-modal-close" onclick="closeMediaModal()" aria-label="Close">&times;</button>
<div id="mediaModalCounter" class="media-modal-counter">1 / 1</div>
<button id="mediaModalPrev" type="button" class="media-modal-arrow media-modal-prev" onclick="changeModalMedia(-1); event.stopPropagation()">‹</button>
<div id="mediaModalContent" class="media-modal-content" onclick="event.stopPropagation()"></div>
<button id="mediaModalNext" type="button" class="media-modal-arrow media-modal-next" onclick="changeModalMedia(1); event.stopPropagation()">›</button>
<div id="mediaModalDots" class="media-modal-dots" onclick="event.stopPropagation()"></div>
</div>
<script>
let activeCarousel=null, activeModalItems=[], activeModalIndex=0;
function carouselItems(c){{try{{return JSON.parse(c.dataset.media||'[]')}}catch(_){{return []}}}}
function showPostMedia(c,i){{const a=carouselItems(c);if(!a.length)return;i=(i+a.length)%a.length;c.dataset.index=i;c.querySelectorAll('.post-carousel-slide').forEach((e,n)=>e.classList.toggle('active',n===i));c.querySelectorAll('.carousel-dot').forEach((e,n)=>e.classList.toggle('active',n===i));const x=c.querySelector('.post-carousel-counter');if(x)x.textContent=(i+1) + " / " + a.length}}
function changePostMedia(c,d){{showPostMedia(c,Number(c.dataset.index||0)+d)}}
function openPostMedia(c,i){{activeCarousel=c;activeModalItems=carouselItems(c);activeModalIndex=i;renderModalMedia();document.getElementById('mediaModal').classList.add('open');document.body.style.overflow='hidden'}}
function renderModalMedia(){{if(!activeModalItems.length)return;activeModalIndex=(activeModalIndex+activeModalItems.length)%activeModalItems.length;const x=activeModalItems[activeModalIndex],box=document.getElementById('mediaModalContent');box.innerHTML='';if(x.type==='video'){{const v=document.createElement('video');v.src=x.url;v.controls=true;v.autoplay=true;v.playsInline=true;box.appendChild(v)}}else{{const im=document.createElement('img');im.src=x.url;im.alt="Media " + (activeModalIndex+1);box.appendChild(im)}}document.getElementById('mediaModalCounter').textContent=(activeModalIndex+1) + " / " + activeModalItems.length;document.getElementById('mediaModalDots').innerHTML='';activeModalItems.forEach((_,i)=>{{const b=document.createElement('button');b.type='button';b.className='media-modal-dot'+(i===activeModalIndex?' active':'');b.onclick=()=>{{activeModalIndex=i;renderModalMedia()}};document.getElementById('mediaModalDots').appendChild(b)}});;document.getElementById('mediaModalPrev').style.display=activeModalItems.length>1?'':'none';document.getElementById('mediaModalNext').style.display=activeModalItems.length>1?'':'none';if(activeCarousel)showPostMedia(activeCarousel,activeModalIndex)}}
function changeModalMedia(d){{activeModalIndex+=d;renderModalMedia()}}
function closeMediaModal(e){{if(e&&e.target&&e.target.id!=='mediaModal'&&!e.target.classList.contains('media-modal-close'))return;document.getElementById('mediaModal').classList.remove('open');document.getElementById('mediaModalContent').innerHTML='';document.body.style.overflow='';activeCarousel=null;activeModalItems=[]}}
document.addEventListener('keydown',e=>{{if(!document.getElementById('mediaModal').classList.contains('open'))return;if(e.key==='Escape')closeMediaModal();if(e.key==='ArrowLeft')changeModalMedia(-1);if(e.key==='ArrowRight')changeModalMedia(1)}});
</script>
</body>
</html>'''


# ============================================================
# PROFILE DISCOVERY
# ============================================================

URL_RE = re.compile(r"https?://[^\s<>'\"]+")


class _ProfileLinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.current = None
        self.text = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        attrs = dict(attrs)
        href = attrs.get("href", "")
        testid = attrs.get("data-testid", "")
        if href and (testid == "UserUrl" or "t.co/" in href):
            self.current = href
            self.text = []

    def handle_data(self, data):
        if self.current is not None:
            self.text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.current is not None:
            self.links.append((self.current, " ".join(self.text).strip()))
            self.current = None
            self.text = []


def _resolve_profile_link(url, base_url):
    url = html.unescape(url).strip()
    if url.startswith("/"):
        url = urljoin(base_url, url)
    if not url.startswith(("http://", "https://")):
        return ""

    host = (urlparse(url).hostname or "").lower()
    blocked = {
        "x.com", "www.x.com", "twitter.com", "www.twitter.com",
        "pbs.twimg.com", "video.twimg.com", "abs.twimg.com",
    }

    if host in blocked:
        return ""

    if host in {"t.co", "www.t.co"}:
        try:
            response = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8,
                allow_redirects=True,
            )
            final = response.url
            final_host = (urlparse(final).hostname or "").lower()
            if final_host and final_host not in blocked | {"t.co", "www.t.co"}:
                return final
        except Exception:
            pass
        return ""

    return url


def _link_label(label, url):
    label = re.sub(r"\s+", " ", html.unescape(label or "")).strip().strip("|•· ")
    if label and len(label) <= 120:
        return label
    return (urlparse(url).hostname or "Website").removeprefix("www.")


def extract_external_links(page, description, profile_url):
    parser = _ProfileLinkParser()
    try:
        parser.feed(page)
    except Exception:
        pass

    result = []
    seen = set()

    for raw, label in parser.links:
        url = _resolve_profile_link(raw, profile_url)
        if not url or url in seen:
            continue
        seen.add(url)
        result.append({"label": _link_label(label, url), "url": url})

    for raw in URL_RE.findall(description or ""):
        url = _resolve_profile_link(raw.rstrip(".,!?;:)"), profile_url)
        if not url or url in seen:
            continue
        seen.add(url)
        result.append({"label": _link_label("", url), "url": url})

    return result[:8]


def discover_profile_data(profile_url):
    result = {"description": "", "photo_url": "", "links": []}

    try:
        response = requests.get(
            profile_url,
            headers={
                "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 Chrome/140.0 Safari/537.36"
            },
            timeout=15,
        )

        if response.status_code != 200:
            return result

        page = response.text

        description_patterns = [
            r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)',
            r'<meta[^>]+property=["\']og:description["\'][^>]+content=["\']([^"\']*)',
            r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+name=["\']description["\']',
            r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']og:description["\']',
        ]

        for pattern in description_patterns:
            match = re.search(pattern, page, re.I)
            if match:
                result["description"] = html.unescape(match.group(1)).strip()
            if result["description"]:
                break

        image_patterns = [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']*)',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']*)',
            r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+property=["\']og:image["\']',
        ]

        for pattern in image_patterns:
            match = re.search(pattern, page, re.I)
            if match:
                result["photo_url"] = html.unescape(match.group(1)).strip()
            if result["photo_url"]:
                break

        result["links"] = extract_external_links(
            page, result["description"], profile_url
        )

    except Exception as exc:
        print(f"[PROFILE] Failed to discover profile data: {exc}")

    return result


def refresh_creator_profile(creator):
    if not creator:
        return

    try:
        data = discover_profile_data(creator["profile_url"])

        if data["description"]:
            update_creator_profile_description(creator["id"], data["description"])
        if data["photo_url"]:
            update_creator_profile_photo(creator["id"], data["photo_url"])
        if data["links"]:
            update_creator_profile_links(creator["id"], data["links"])

    except Exception as exc:
        print(f"[PROFILE] Refresh failed: {exc}")


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
def startup():
    init_database()
    GALLERY_DIR.mkdir(parents=True, exist_ok=True)
    start_scheduler()


@app.on_event("shutdown")
def shutdown():
    stop_scheduler()


# ============================================================
# HOME / ADD CREATOR
# ============================================================

@app.get("/", response_class=HTMLResponse)
def home():
    creators = get_creators()

    content = '''<h1>MediaVault</h1>
<p class="muted">Local media archive for X creators.</p>
<div class="card" style="margin:20px 0">
    <h2>Add Creator</h2>
    <form method="post" action="/creators/add">
        <div class="form-group">
            <input type="url" name="profile_url" placeholder="https://x.com/username" required>
        </div>
        <button class="primary" type="submit">Add Creator</button>
    </form>
</div>'''

    if not creators:
        content += '''<div class="empty-state">
            <h2>No creators yet</h2>
            <p>Add an X creator above to start archiving.</p>
        </div>'''
    else:
        content += '<h2 class="section-title">Creators</h2><div class="grid">'

        for creator in creators:
            cid = creator["id"]
            name = creator_name(creator)
            username = creator_username(creator)
            photo = creator.get("profile_photo_url") or ""

            avatar = (
                f'<img class="creator-profile-image" src="{escape_html(photo)}" loading="lazy">'
                if photo
                else '<div class="creator-profile-image creator-profile-placeholder">𝕏</div>'
            )

            desc = render_description(creator.get("profile_description") or "")

            content += f'''
<div class="card creator-card">
    <div style="display:flex;gap:12px;align-items:center">
        {avatar}
        <div>
            <div class="creator-name">{escape_html(name)}</div>
            <div class="creator-username">{escape_html("@" + username if username else "")}</div>
        </div>
    </div>
    {f'<div class="creator-description">{desc}</div>' if desc else ''}
    {profile_links_html(creator)}
    <div class="actions">
        <a class="button primary" href="/creator/{cid}">Open</a>
        <form class="inline" method="post" action="/creators/{cid}/sync">
            <button type="submit">Sync</button>
        </form>
        <form class="inline" method="post" action="/creators/{cid}/delete"
              onsubmit="return confirm('Delete this creator and all archived media?')">
            <button class="danger" type="submit">Delete</button>
        </form>
    </div>
</div>'''

        content += '</div>'

    return HTMLResponse(render_page("Home", content))


@app.post("/creators/add")
def create_creator(profile_url: str = Form(...)):
    profile_url = profile_url.strip()

    if not profile_url:
        return RedirectResponse("/", status_code=303)

    if not profile_url.startswith(("http://", "https://")):
        profile_url = "https://" + profile_url

    profile_url = profile_url.rstrip("/")
    match = re.search(r"x\.com/([^/?#]+)", profile_url, re.IGNORECASE)
    username = match.group(1) if match else ""

    try:
        creator_id = add_creator("x", username, profile_url, username)
        data = discover_profile_data(profile_url)

        if data["description"]:
            update_creator_profile_description(creator_id, data["description"])
        if data["photo_url"]:
            update_creator_profile_photo(creator_id, data["photo_url"])
        if data["links"]:
            update_creator_profile_links(creator_id, data["links"])

    except Exception as exc:
        print(f"[CREATOR] Add/profile discovery failed: {exc}")
        return RedirectResponse("/", status_code=303)

    return RedirectResponse(f"/creator/{creator_id}", status_code=303)


# ============================================================
# GALLERY
# ============================================================

def gallery_panel(posts):
    items = []

    for post in posts:
        for path in get_post_files(post):
            url = local_file_url(path)
            if not url:
                continue

            suffix = path.suffix.lower()

            if suffix in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
                items.append(
                    f'<button type="button" class="gallery-item" '
                    f'onclick="openMediaModal(\'{escape_html(url)}\', \'image\')">'
                    f'<img class="gallery-thumb" src="{escape_html(url)}" loading="lazy">'
                    f'</button>'
                )

            elif suffix in {".mp4", ".webm", ".mov", ".mkv"}:
                items.append(
                    f'<button type="button" class="gallery-item" '
                    f'onclick="openMediaModal(\'{escape_html(url)}\', \'video\')">'
                    f'<video class="gallery-thumb" muted preload="metadata">'
                    f'<source src="{escape_html(url)}"></video></button>'
                )

    return "".join(items) or '<div class="gallery-empty">No archived media yet.</div>'


@app.get("/creator/{creator_id}/gallery", response_class=HTMLResponse)
def creator_gallery_page(creator_id: int):
    creator = get_creator(creator_id)

    if not creator:
        return RedirectResponse("/", status_code=303)

    posts = get_creator_posts(creator_id)
    name = creator_name(creator)
    media_count = sum(len(get_post_files(post)) for post in posts)

    content = f'''
<div class="gallery-page-header">
    <div>
        <h1 class="gallery-page-title">{escape_html(name)} Gallery</h1>
        <div class="muted">{media_count} media files</div>
    </div>
    <a class="button" href="/creator/{creator_id}">Back to Creator</a>
</div>

<div class="gallery-panel">
    <div class="gallery-grid">
        {gallery_panel(posts)}
    </div>
</div>'''

    return HTMLResponse(render_page(f"{name} Gallery", content))


# ============================================================
# CREATOR PAGE
# ============================================================

@app.get("/creator/{creator_id}", response_class=HTMLResponse)
def creator_page(creator_id: int):
    creator = get_creator(creator_id)

    if not creator:
        return RedirectResponse("/", status_code=303)

    posts = get_creator_posts(creator_id)
    name = creator_name(creator)
    username = creator_username(creator)
    photo = creator.get("profile_photo_url") or ""

    avatar = (
        f'<img class="creator-profile-image" src="{escape_html(photo)}" loading="lazy">'
        if photo
        else '<div class="creator-profile-image creator-profile-placeholder">𝕏</div>'
    )

    desc = render_description(creator.get("profile_description") or "")

    content = f'''
<div class="creator-page-header">
    {avatar}
    <div class="creator-page-info">
        <div class="creator-page-name">{escape_html(name)}</div>
        <div class="creator-page-username">{escape_html("@" + username if username else "")}</div>
    </div>

    <div class="creator-header-actions">
        <a class="button primary" href="/creator/{creator_id}/gallery">Open Gallery</a>
        <a class="button" href="{escape_html(creator.get("profile_url", "#"))}" target="_blank" rel="noopener noreferrer">Open X</a>
    </div>
</div>

<div class="profile-panel">
    {f'<div class="creator-page-description">{desc}</div>' if desc else ''}
    {profile_links_html(creator)}
</div>

<div class="actions">
    <form class="inline" method="post" action="/creators/{creator_id}/sync">
        <button class="primary">Sync New Posts</button>
    </form>
    <form class="inline" method="post" action="/creators/{creator_id}/import-older">
        <button>Import Older Posts</button>
    </form>
    <form class="inline" method="post" action="/creators/{creator_id}/refresh-profile">
        <button>Refresh Profile</button>
    </form>
    <form class="inline" method="post" action="/creators/{creator_id}/delete"
          onsubmit="return confirm('Delete this creator and all archived media?')">
        <button class="danger">Delete Creator</button>
    </form>
</div>

<h2 class="section-title">Posts</h2>'''

    if not posts:
        content += '''<div class="empty-state">
            <h2>No posts</h2>
            <p>Run Sync New Posts to download posts.</p>
        </div>'''
    else:
        post_grid_class = "single-post-grid" if len(posts) == 1 else "multi-post-grid"
        content += f'<div class="post-grid {post_grid_class}">'

        for post in posts:
            pid = post["id"]
            description = render_description(post.get("description") or "")
            description_html = (
                f'<div class="post-description">{description}</div>'
                if description else ""
            )

            content += f'''
<article class="post-card">
    <div class="post-media">{media_html(post)}</div>
    <div class="post-body">
        {description_html}
        <div class="post-meta">{escape_html(post.get("created_at") or "")}</div>
        <div class="actions" style="margin-top:10px">
            <form class="inline" method="post" action="/posts/{pid}/delete">
                <button class="danger">Delete Post</button>
            </form>
        </div>
    </div>
</article>'''

        content += '</div>'

    return HTMLResponse(render_page(name, content))


# ============================================================
# SYNC / PROFILE
# ============================================================

@app.post("/creators/{creator_id}/sync")
def sync_creator_route(creator_id: int):
    if not get_creator(creator_id):
        return RedirectResponse("/", status_code=303)

    try:
        result = sync_creator(creator_id)
        print(f"[SYNC] Creator {creator_id}: {result}")

        if not result.get("cancelled"):
            creator = get_creator(creator_id)
            if creator:
                refresh_creator_profile(creator)

    except Exception as exc:
        print(f"[SYNC] Creator {creator_id} failed: {exc}")

    return RedirectResponse(f"/creator/{creator_id}", status_code=303)


@app.post("/creators/{creator_id}/refresh-profile")
def refresh_profile_route(creator_id: int):
    creator = get_creator(creator_id)

    if creator:
        refresh_creator_profile(creator)

    return RedirectResponse(f"/creator/{creator_id}", status_code=303)


# ============================================================
# OLDER IMPORT
# ============================================================

@app.post("/creators/{creator_id}/import-older")
def import_older_posts(creator_id: int):
    creator = get_creator(creator_id)

    if not creator:
        return RedirectResponse("/", status_code=303)

    start_task(creator_id)
    clear_cancel(creator_id)
    imported = 0
    discovered = 0

    try:
        for post in iter_older_creator_posts(
            creator["profile_url"],
            limit=None,
            creator_id=creator_id,
        ):
            if is_cancelled(creator_id):
                break

            discovered += 1
            post_id = str(post.get("post_id") or post.get("id") or "")

            if not post_id or is_post_deleted(creator_id, post_id):
                continue

            existing = None
            connection = sqlite3.connect(DATABASE_PATH)
            connection.row_factory = sqlite3.Row

            try:
                row = connection.execute(
                    "SELECT * FROM posts WHERE creator_id=? AND platform_post_id=?",
                    (creator_id, post_id),
                ).fetchone()
                existing = dict(row) if row else None
            finally:
                connection.close()

            if existing:
                folder = Path(existing.get("folder_path") or "")

                try:
                    download_gallery_media(post, folder, creator_id=creator_id)

                    if not is_cancelled(creator_id):
                        save_post_metadata(folder, post)
                        record_media_files(existing["id"], folder)

                except Exception:
                    remove_incomplete_downloads(folder)
                    if is_cancelled(creator_id):
                        break
                    raise

                continue

            name = (
                post.get("creator")
                or post.get("creator_name")
                or creator.get("display_name")
                or creator.get("username")
                or f"creator_{creator_id}"
            )

            date = str(post.get("upload_date") or post.get("date") or "")
            date_folder = (
                f"{date[:4]}-{date[4:6]}-{date[6:8]}"
                if len(date) == 8
                else "unknown_date"
            )

            folder = (
                GALLERY_DIR
                / safe_name(name)
                / date_folder
                / f"post_{safe_name(post_id)}"
            )
            folder.mkdir(parents=True, exist_ok=True)

            try:
                download_gallery_media(post, folder, creator_id=creator_id)

                if is_cancelled(creator_id):
                    remove_incomplete_downloads(folder)
                    break

                save_post_metadata(folder, post)

                if is_cancelled(creator_id):
                    remove_incomplete_downloads(folder)
                    break

                db_id = add_post(
                    creator_id,
                    post_id,
                    post.get("post_url") or post.get("url") or "",
                    post.get("description") or "",
                    post.get("upload_date") or post.get("date") or "",
                    str(folder),
                )

                record_media_files(db_id, folder)
                imported += 1

            except Exception:
                remove_incomplete_downloads(folder)

                if is_cancelled(creator_id):
                    break

                raise

    except Exception as exc:
        print(f"[OLDER] Import failed for creator {creator_id}: {exc}")

    finally:
        print(
            f"[OLDER] Creator {creator_id}: "
            f"discovered={discovered}, imported={imported}, "
            f"cancelled={is_cancelled(creator_id)}"
        )
        finish_task(creator_id)

    return RedirectResponse(f"/creator/{creator_id}", status_code=303)


# ============================================================
# CHECK CREATOR
# ============================================================

@app.get("/creators/check")
def check_creator(profile_url: str):
    try:
        posts = discover_creator_posts(profile_url)
        return {
            "profile_url": profile_url,
            "post_count": len(posts),
            "posts": posts,
        }
    except Exception as exc:
        return {
            "profile_url": profile_url,
            "post_count": 0,
            "posts": [],
            "error": str(exc),
        }


# ============================================================
# DELETE POST / CREATOR
# ============================================================

@app.post("/posts/{post_id}/delete")
def delete_post_route(post_id: int):
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row

    try:
        row = connection.execute(
            "SELECT * FROM posts WHERE id=?",
            (post_id,),
        ).fetchone()
    finally:
        connection.close()

    post = dict(row) if row else None

    if not post:
        return RedirectResponse("/", status_code=303)

    if post.get("folder_path"):
        try:
            folder = Path(post["folder_path"])
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)
        except Exception as exc:
            print(f"[DELETE POST] Failed to remove files: {exc}")

    delete_post(post_id)
    return RedirectResponse(f"/creator/{post['creator_id']}", status_code=303)


@app.post("/creators/{creator_id}/delete")
def delete_creator_route(creator_id: int):
    creator = get_creator(creator_id)

    if not creator:
        return RedirectResponse("/", status_code=303)

    # Stop any running sync/import before deleting local files.
    request_cancel(creator_id)

    for _ in range(300):
        if not is_task_running(creator_id):
            break
        time.sleep(0.1)

    # Remove every folder known by the database.
    folders = {
        Path(post["folder_path"])
        for post in get_creator_posts(creator_id)
        if post.get("folder_path")
    }

    for folder in folders:
        try:
            if folder.exists():
                shutil.rmtree(folder, ignore_errors=True)
        except Exception as exc:
            print(f"[DELETE CREATOR] Could not remove {folder}: {exc}")

    # Also remove the complete creator directory.
    # This catches orphaned folders/files that are not in SQLite.
    creator_folder = GALLERY_DIR / safe_name(creator_name(creator))

    try:
        if creator_folder.exists():
            shutil.rmtree(creator_folder, ignore_errors=True)
            print(f"[DELETE CREATOR] Removed local gallery: {creator_folder}")
    except Exception as exc:
        print(f"[DELETE CREATOR] Could not remove creator gallery: {exc}")

    # Remove creator and related database records.
    delete_creator(creator_id)

    return RedirectResponse("/", status_code=303)
