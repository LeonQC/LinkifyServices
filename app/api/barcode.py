from fastapi import APIRouter, HTTPException, status, Response
from app.core.config import settings
from app.models import Barcode
from app.services.barcode_service import create_barcode_logic, get_all_barcodes_for_user
from app.utils.barcode_utils import to_barcode
from app.utils.cache import cache_get_s3_url, cache_set_s3_url
from app.utils.s3_utils import get_image_from_s3
from app.celery_app import get_task_info
from app.celery_tasks.tasks import create_barcode_task
from starlette.responses import JSONResponse
from app.utils.redirect_utils import redirect_to_original
# Use shared dependencies
from app.core.dependencies import db_dependency, user_dependency
# Request / Response Models
from app.schemas.barcode import BarcodeRequest

router = APIRouter(
    prefix="/barcodes",
    tags=["barcodes"]
)


# ---------- Endpoints ----------

# 1. Read all barcodes for user
@router.get("/", status_code=status.HTTP_200_OK)
async def read_all(user: user_dependency, db: db_dependency):
    return get_all_barcodes_for_user(user.get('id'), db)


# 2. Generate Barcode
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_barcode(
    user: user_dependency,
    req: BarcodeRequest,
    db: db_dependency
):
    try:
        return create_barcode_logic(user.get("id"), req, db)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


# 2.b. Generate Barcode (async via Celery)

# 4.1.b. Generate Barcode (Async, Celery)
@router.post("/async", status_code=status.HTTP_202_ACCEPTED)
async def create_barcode_async(
    user: user_dependency,
    req: BarcodeRequest
):
    task = create_barcode_task.apply_async(args=[user.get("id"), req.model_dump()])
    return {
        "success": True,
        "task_id": task.id,
        "status": "pending",
        "poll_url": f"{settings.base_url}/barcodes/task/{task.id}"
    }


# Task status

# 4.4. Get Barcode Task Status (Celery)
@router.get("/task/{task_id}")
async def get_barcode_task_status(task_id: str):
    info = get_task_info(task_id)
    error = None
    if info["task_status"] == "FAILURE":
        error = str(info["task_result"])
    return {
        "success": info["task_status"] == "SUCCESS",
        "task_id": info["task_id"],
        "status": info["task_status"],
        "result": info["task_result"] if info["task_status"] == "SUCCESS" else None,
        "error": error,
        "poll_url": f"{settings.base_url}/barcodes/task/{task_id}"
    }


# 3. Get Barcode Image
@router.get("/{barcode_id}/image")
async def get_barcode_image(barcode_id: str, db: db_dependency):
    cache_key = f"barcode:s3key:{barcode_id}"
    cached_url = cache_get_s3_url(cache_key)
    s3_key = None
    if cached_url:
        prefix = settings.s3_base_url.rstrip('/')
        if cached_url.startswith(prefix):
            s3_key = cached_url[len(prefix):].lstrip('/')
        else:
            s3_key = cached_url.rsplit('/', 1)[-1]
    else:
        obj = db.query(Barcode).filter(Barcode.barcode_id == barcode_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="Barcode not found")
        s3_key = obj.s3_key
        s3_url = f"{settings.s3_base_url}/{s3_key}"
        cache_set_s3_url(cache_key, s3_url, ttl_seconds=3600)
    try:
        img_bytes = get_image_from_s3(s3_key)
    except Exception:
        raise HTTPException(status_code=404, detail="Barcode image not found in S3")
    return Response(content=img_bytes, media_type="image/png")


# 4. Redirect from Barcode
@router.get("/{barcode_id}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
async def redirect_from_barcode(barcode_id: str, db: db_dependency):
    obj = db.query(Barcode).filter(Barcode.barcode_id == barcode_id).first()
    if obj:
        obj.scans += 1
        db.commit()
    return redirect_to_original(obj)
