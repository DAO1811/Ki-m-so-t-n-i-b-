"""Private attachments on owner-authorized Drive; database bytes only in development."""

import warnings
from hashlib import sha256
from io import BytesIO
from pathlib import PurePath

from defusedxml import ElementTree
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from PIL import Image, ImageOps
from pypdf import PdfReader

from .models import MediaQuota, ProductPhoto, ReceiptAttachment, StoredFile

MAX_UPLOAD = 8 * 1024 * 1024


def validate_upload(upload, *, photo=False):
    if upload.size > MAX_UPLOAD:
        raise ValidationError("Tệp tối đa 8 MB. Hãy giảm kích thước hoặc chia hồ sơ.")
    content = upload.read(MAX_UPLOAD + 1)
    upload.seek(0)
    if not content or len(content) > MAX_UPLOAD:
        raise ValidationError("Tệp trống hoặc quá lớn.")
    extension = PurePath(upload.name).suffix.lower()
    if extension in [".jpg", ".jpeg", ".png", ".webp"]:
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(BytesIO(content)) as image:
                    if (
                        image.format not in ["JPEG", "PNG", "WEBP"]
                        or image.width * image.height > 20_000_000
                    ):
                        raise ValueError
                    image.verify()
                with Image.open(BytesIO(content)) as image:
                    if photo:
                        image = ImageOps.exif_transpose(image)
                        image.thumbnail((1600, 1600))
                        output = BytesIO()
                        image.convert("RGB").save(
                            output, format="JPEG", quality=82, optimize=True
                        )
                        content = output.getvalue()
                        if len(content) > 2 * 1024 * 1024:
                            raise ValueError
                        content_type = "image/jpeg"
                    else:
                        content_type = Image.MIME[image.format]
        except Exception as exc:
            raise ValidationError(
                "Ảnh không hợp lệ hoặc quá lớn. Dùng JPG, PNG hoặc WebP, tối đa 20 triệu điểm ảnh."
            ) from exc
    elif not photo and extension == ".pdf":
        try:
            if not content.startswith(b"%PDF-"):
                raise ValueError
            reader = PdfReader(BytesIO(content), strict=True)
            if reader.is_encrypted or not 0 < len(reader.pages) <= 200:
                raise ValueError
        except Exception as exc:
            raise ValidationError(
                "PDF không đọc được, có mật khẩu hoặc quá 200 trang."
            ) from exc
        content_type = "application/pdf"
    elif not photo and extension == ".xml":
        try:
            ElementTree.fromstring(content)
        except Exception as exc:
            raise ValidationError(
                "XML không hợp lệ hoặc chứa thực thể ngoài không được phép."
            ) from exc
        content_type = "application/xml"
    else:
        raise ValidationError(
            "Dùng ảnh JPG/PNG/WebP"
            + (
                "."
                if photo
                else ", PDF hoặc XML. Không nhận tệp thực thi, SVG hoặc HTML."
            )
        )
    return content, content_type


@transaction.atomic
def store_file(validated, context, filename):
    content, content_type = validated
    MediaQuota.objects.get_or_create(pk=1)
    MediaQuota.objects.select_for_update().get(pk=1)
    digest = sha256(content).hexdigest()
    context_key = context["kind"] + ":" + context["key"]
    existing = (
        StoredFile.objects.only("id")
        .filter(sha256=digest, context_key=context_key)
        .first()
    )
    if existing:
        return existing
    if settings.PRIVATE_MEDIA_PROVIDER == "drive":
        from .drive import upload

        drive_id = upload(content, content_type, digest, context, filename)
        return StoredFile.objects.create(
            sha256=digest,
            context_key=context_key,
            provider="drive",
            drive_id=drive_id,
            content_type=content_type,
            size=len(content),
        )
    if not settings.DEBUG or settings.PRIVATE_MEDIA_PROVIDER != "database":
        raise ValidationError(
            "Bản online phải dùng Google Drive đã kết nối; không lưu tệp vào database hoặc ổ đĩa tạm."
        )
    used = (
        StoredFile.objects.filter(provider="database").aggregate(n=Sum("size"))["n"]
        or 0
    )
    if used + len(content) > settings.PRIVATE_MEDIA_LIMIT_BYTES:
        raise ValidationError(
            "Đã chạm hạn mức tệp của phần mềm. Không lưu được tệp mới; quản trị viên cần kiểm tra dung lượng trước khi tăng hạn mức."
        )
    return StoredFile.objects.create(
        sha256=digest,
        context_key=context_key,
        provider="database",
        content_type=content_type,
        size=len(content),
        data=content,
    )


@transaction.atomic
def add_product_photo(product, user, validated, caption=""):
    type(product).objects.select_for_update().get(pk=product.pk)
    existing = ProductPhoto.objects.filter(
        product=product, file__sha256=sha256(validated[0]).hexdigest()
    ).first()
    if existing:
        return existing
    if product.photos.count() >= 5:
        raise ValidationError("Mỗi mã hàng tối đa 5 ảnh.")
    file = store_file(
        validated,
        {"kind": "product", "key": str(product.qr_token), "name": product.sku},
        "anh-hang-hoa-" + sha256(validated[0]).hexdigest()[:12] + ".jpg",
    )
    existing = ProductPhoto.objects.filter(product=product, file=file).first()
    if existing:
        return existing
    if product.photos.count() >= 5:
        raise ValidationError(
            "Mỗi mã hàng tối đa 5 ảnh. Ảnh đã lưu được giữ để đối chiếu."
        )
    return ProductPhoto.objects.create(
        product=product, file=file, uploaded_by=user, caption=caption
    )


@transaction.atomic
def add_receipt_attachment(doc, user, validated, upload_name, **metadata):
    from .models import Document

    doc = Document.objects.select_for_update().get(pk=doc.pk)
    if doc.kind != "IN" or doc.status == "CANCELLED":
        raise ValidationError("Chỉ thêm hồ sơ vào phiếu nhập chưa hủy.")
    from django.core.exceptions import PermissionDenied

    from .access import may_attach
    from .services import documents_for

    if not documents_for(user).filter(pk=doc.pk).exists() or not may_attach(doc, user):
        raise PermissionDenied
    existing = ReceiptAttachment.objects.filter(
        document=doc,
        file__sha256=sha256(validated[0]).hexdigest(),
        voided_at__isnull=True,
    ).first()
    if existing:
        return existing
    if doc.attachments.count() >= 20:
        raise ValidationError("Mỗi đợt nhập tối đa 20 tệp hồ sơ.")
    filename = (
        "".join(
            c
            for c in str(upload_name).replace(chr(92), "/").split("/")[-1]
            if ord(c) >= 32 and ord(c) != 127
        )[:150]
        or "ho-so"
    )
    file = store_file(
        validated,
        {
            "kind": "receipt",
            "key": str(doc.pk),
            "name": f"PK-{doc.pk:06d}",
            "year": str(doc.business_date.year),
        },
        filename,
    )
    existing = ReceiptAttachment.objects.filter(
        document=doc, file=file, voided_at__isnull=True
    ).first()
    if existing:
        return existing
    if doc.attachments.count() >= 20:
        raise ValidationError("Mỗi đợt nhập tối đa 20 tệp hồ sơ.")
    attachment = ReceiptAttachment.objects.create(
        document=doc, file=file, uploaded_by=user, filename=filename, **metadata
    )
    from .services import audit_document

    audit_document(
        doc,
        user,
        "FILE_ADD",
        {
            "attachment": {
                "id": attachment.pk,
                "filename": filename,
                "invoice_number": attachment.invoice_number,
                "sha256": file.sha256,
            }
        },
    )
    return attachment
