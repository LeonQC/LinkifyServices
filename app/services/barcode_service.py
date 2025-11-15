from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import Barcode
from app.schemas.barcode import BarcodeRequest, BarcodeResponse
from app.utils.barcode_utils import to_barcode
from app.utils.random_id import generate_random_id
from app.core.config import settings
from typing import Optional

def create_barcode_logic(user_id: int, req: BarcodeRequest, db: Session) -> BarcodeResponse:
    from app.utils.s3_utils import upload_image_to_s3, generate_presigned_url
    from app.utils.cache import cache_set_s3_url
    for _ in range(5):
        barcode_id = generate_random_id(10)
        buffer = to_barcode(original_url=str(req.original_url))
        img_bytes = buffer.getvalue()
        s3_key = upload_image_to_s3(img_bytes, prefix="barcode")
        barcode = Barcode(
            original_url=str(req.original_url),
            title=req.title,
            description=req.description,
            user_id=user_id,
            barcode_id=barcode_id,
            s3_key=s3_key
        )
        db.add(barcode)
        try:
            db.commit()
            db.refresh(barcode)
            break
        except IntegrityError:
            db.rollback()
    else:
        raise ValueError("Failed to generate unique barcode_id after several attempts.")

    cache_key = f"barcode:s3key:{barcode.barcode_id}"
    s3_image_url = generate_presigned_url(barcode.s3_key)
    cache_set_s3_url(cache_key, s3_image_url, ttl_seconds=300)
    return BarcodeResponse(
        original_url=barcode.original_url,
        barcode_id=barcode.barcode_id,
        image_url=s3_image_url,
        title=barcode.title,
        description=barcode.description,
        scans=barcode.scans,
        user_id=barcode.user_id,
        created_at=barcode.created_at.isoformat()
    )

def get_all_barcodes_for_user(user_id: int, db: Session):
    return db.query(Barcode).filter(Barcode.user_id == user_id).all()
