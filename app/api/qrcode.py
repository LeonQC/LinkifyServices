from fastapi import APIRouter, HTTPException, status, Response
from app.models import Qrcode
from app.core.config import settings
from app.services.qrcode_service import create_qrcode_logic, get_all_qrcodes_for_user
from app.celery_app import get_task_info
from app.celery_tasks.tasks import create_qrcode_task
from starlette.responses import JSONResponse
from app.utils.qrcode_utils import to_qr_code
from app.utils.cache import cache_get_s3_url, cache_set_s3_url
from app.utils.s3_utils import get_image_from_s3
from app.utils.redirect_utils import redirect_to_original
from app.core.dependencies import db_dependency, user_dependency
from app.schemas.qrcode import QRCodeRequest


router = APIRouter(
	prefix="/qrcodes",
	tags=["qrcodes"]
)



@router.get("/", status_code=status.HTTP_200_OK)
async def read_all(user: user_dependency, db: db_dependency):
	return get_all_qrcodes_for_user(user.get('id'), db)

# 3.1. Generate QR Code
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_qrcode(
	user: user_dependency,
	req: QRCodeRequest,
	db: db_dependency
):
	try:
		return create_qrcode_logic(user.get("id"), req, db)
	except ValueError as e:
		raise HTTPException(status_code=409, detail=str(e))


# 3.1.b. Generate QR Code (async via Celery)

# 3.1.b. Generate QR Code (Async, Celery)
@router.post("/async", status_code=status.HTTP_202_ACCEPTED)
async def create_qrcode_async(
    user: user_dependency,
    req: QRCodeRequest
):
    task = create_qrcode_task.apply_async(args=[user.get("id"), req.model_dump()])
    return {
        "success": True,
        "task_id": task.id,
        "status": "pending",
        "poll_url": f"{settings.base_url}/qrcodes/task/{task.id}"
    }


# Task status

# 3.4. Get QR Code Task Status (Celery)
@router.get("/task/{task_id}")
async def get_qrcode_task_status(task_id: str):
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
        "poll_url": f"{settings.base_url}/qrcodes/task/{task_id}"
    }


# 3.2. Get QR Code Image
@router.get("/{qr_code_id}/image")
async def get_qrcode_image(qr_code_id: str, db: db_dependency):
    cache_key = f"qrcode:s3key:{qr_code_id}"
    cached_url = cache_get_s3_url(cache_key)
    s3_key = None
    if cached_url:
        # cached value is full S3 URL; extract key relative to settings.s3_base_url
        prefix = settings.s3_base_url.rstrip('/')
        if cached_url.startswith(prefix):
            s3_key = cached_url[len(prefix):].lstrip('/')
        else:
            # fallback: take last path segment
            s3_key = cached_url.rsplit('/', 1)[-1]
    else:
        obj = db.query(Qrcode).filter(Qrcode.qr_code_id == qr_code_id).first()
        if not obj:
            raise HTTPException(status_code=404, detail="QR Code not found")
        s3_key = obj.s3_key
        s3_url = f"{settings.s3_base_url}/{s3_key}"
        cache_set_s3_url(cache_key, s3_url, ttl_seconds=3600)
    try:
        img_bytes = get_image_from_s3(s3_key)
    except Exception:
        raise HTTPException(status_code=404, detail="QR Code image not found in S3")
    return Response(content=img_bytes, media_type="image/png")


# 3.3. Redirect from QR Code
@router.get("/{qr_code_id}", status_code=status.HTTP_307_TEMPORARY_REDIRECT)
async def redirect_from_qrcode(qr_code_id: str, db: db_dependency):
    obj = db.query(Qrcode).filter(Qrcode.qr_code_id == qr_code_id).first()
    if obj:
        obj.scans += 1
        db.commit()
    return redirect_to_original(obj)
