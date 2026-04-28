from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import Qrcode
from app.schemas.qrcode import QRCodeRequest, QRCodeResponse
from app.utils.qrcode_utils import to_qr_code
from app.utils.random_id import generate_random_id
from app.core.config import settings
from typing import Optional

def create_qrcode_logic(user_id: int, req: QRCodeRequest, db: Session) -> QRCodeResponse:
    from app.utils.s3_utils import upload_image_to_s3, generate_presigned_url
    from app.utils.cache import cache_set_s3_url
    for _ in range(5):
        qr_code_id = generate_random_id(10)
        buffer = to_qr_code(original_url=str(req.original_url))
        img_bytes = buffer.getvalue()
        s3_key = upload_image_to_s3(img_bytes, prefix="qrcode")
        qr_code = Qrcode(
            original_url=str(req.original_url),
            title=req.title,
            description=req.description,
            user_id=user_id,
            qr_code_id=qr_code_id,
            s3_key=s3_key
        )
        db.add(qr_code)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue
        db.refresh(qr_code)
        break
    else:
        raise ValueError("Failed to generate unique QR code ID after several attempts.")

    cache_key = f"qrcode:s3key:{qr_code.qr_code_id}"
    # 为私有对象生成可临时访问的预签名 URL
    s3_image_url = generate_presigned_url(qr_code.s3_key)
    # Cache the pre-signed URL (短期缓存，过期后会自动失效)
    cache_set_s3_url(cache_key, s3_image_url, ttl_seconds=300)
    return QRCodeResponse(
        original_url=qr_code.original_url,
        qr_code_id=qr_code.qr_code_id,
        image_url=s3_image_url,
        title=qr_code.title,
        description=qr_code.description,
        scans=qr_code.scans,
        user_id=qr_code.user_id,
        created_at=qr_code.created_at.isoformat()
    )

def get_all_qrcodes_for_user(user_id: int, db: Session):
    return db.query(Qrcode).filter(Qrcode.user_id == user_id).all()
