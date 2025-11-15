from fastapi import APIRouter, HTTPException, Query
from pydantic import AnyUrl
from app.services.metadata_service import fetch_metadata_logic
from fastapi import Query, Response, HTTPException
from app.utils.metadata_utils import extract_preview_image_url
import requests
from urllib.parse import urlparse

router = APIRouter(
    prefix="/metadata",
    tags=["metadata"]
)

@router.get("/", status_code=200)
async def get_metadata(url: AnyUrl = Query(..., description="Target URL to fetch metadata")):
    try:
        return fetch_metadata_logic(str(url))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch metadata: {str(e)}")


@router.get("/image", status_code=200)
async def get_preview_image(
    url: AnyUrl = Query(..., description="Target URL to fetch preview image from"),
    redirect: bool = Query(False, description="If true, return a redirect to the preview image URL instead of proxying bytes")
):
    """Return the link preview image for `url`.

    If `redirect=true`, responds with a 307 redirect to the image URL (if found).
    Otherwise proxies the image bytes and returns them with the original content-type.
    """
    try:
        img_url = extract_preview_image_url(str(url))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse target page: {e}")

    if not img_url:
        raise HTTPException(status_code=404, detail="No preview image found")

    if redirect:
        # Return redirect to image URL
        return Response(status_code=307, headers={"Location": img_url})

    # Proxy the image bytes
    try:
        r = requests.get(img_url, timeout=10, stream=True)
        r.raise_for_status()
    except Exception:
        raise HTTPException(status_code=502, detail="Failed to fetch preview image")

    content_type = r.headers.get("content-type", "application/octet-stream")
    content = r.content
    return Response(content=content, media_type=content_type)
