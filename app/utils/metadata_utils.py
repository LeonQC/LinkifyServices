import requests
from bs4 import BeautifulSoup
from typing import Optional
from urllib.parse import urljoin

def fetch_url_metadata(url: str) -> dict:
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    title = soup.title.string if soup.title else None
    description = soup.find("meta", attrs={"name": "description"})
    description = description["content"] if description else None

    return {
        "title": title,
        "description": description,
    }


def extract_preview_image_url(url: str) -> Optional[str]:
    """Return a best-effort preview image URL from the target page, or None.

    Checks Open Graph, Twitter cards, and common link rels.
    """
    try:
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
    except Exception:
        return None

    soup = BeautifulSoup(resp.text, "html.parser")

    # Common meta tags for preview images
    candidates = []
    og = soup.find("meta", property="og:image")
    if og and og.get("content"):
        candidates.append(og.get("content"))
    twitter = soup.find("meta", attrs={"name": "twitter:image"})
    if twitter and twitter.get("content"):
        candidates.append(twitter.get("content"))
    img_link = soup.find("link", rel="image_src")
    if img_link and img_link.get("href"):
        candidates.append(img_link.get("href"))

    # Also try the largest <img> on the page as a fallback
    if not candidates:
        imgs = soup.find_all("img", src=True)
        if imgs:
            # pick the first non-empty src
            for img in imgs:
                src = img.get("src")
                if src:
                    candidates.append(src)
                    break

    for cand in candidates:
        if not cand:
            continue
        # Make absolute URL
        img_url = urljoin(url, cand)
        return img_url
    return None
