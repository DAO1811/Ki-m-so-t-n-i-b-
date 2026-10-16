from io import BytesIO
from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
import qrcode

from .forms import ProductPhotoForm, ReceiptAttachmentForm
from .media import add_product_photo, add_receipt_attachment
from .models import Product, ProductPhoto, StoredFile, ReceiptAttachment, Line, Balance
from .services import documents_for, warehouses_for


from .access import may_attach


@login_required
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    receipts = (
        Line.objects.filter(
            product=product, document__in=documents_for(request.user).filter(kind="IN")
        )
        .select_related("document__destination", "document__created_by")
        .prefetch_related("document__attachments")
        .order_by("-document__business_date", "-document_id")
    )
    page = Paginator(receipts, 20).get_page(request.GET.get("page"))
    return render(
        request,
        "product_detail.html",
        {
            "product": product,
            "photos": product.photos.all(),
            "receipts": page,
            "page_obj": page,
            "photo_form": ProductPhotoForm(),
            "balances": Balance.objects.filter(
                product=product, warehouse__in=warehouses_for(request.user)
            ).select_related("warehouse"),
        },
    )


@login_required
def qr_landing(request, token):
    return redirect("product_detail", pk=get_object_or_404(Product, qr_token=token).pk)


@login_required
def product_qr(request, pk):
    product = get_object_or_404(Product, pk=pk)
    target = request.build_absolute_uri(reverse("qr_landing", args=[product.qr_token]))
    output = BytesIO()
    qrcode.make(target).save(output, format="PNG")
    response = HttpResponse(output.getvalue(), content_type="image/png")
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def product_labels(request):
    ids = request.GET.getlist("id")
    if len(ids) > 100 or any(not value.isdigit() or len(value) > 18 for value in ids):
        return HttpResponse("Mỗi lần in tối đa 100 mã hàng hợp lệ.", status=400)
    qs = Product.objects.filter(pk__in=ids) if ids else Product.objects.all()
    return render(
        request, "product_labels.html", {"products": qs.order_by("sku")[:100]}
    )


@login_required
@require_POST
@permission_required("inventory.change_product", raise_exception=True)
def product_photo_add(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductPhotoForm(request.POST, request.FILES)
    if form.is_valid() and form.cleaned_data.get("image"):
        try:
            add_product_photo(
                product,
                request.user,
                form.validated_image,
                form.cleaned_data["caption"],
            )
            messages.success(request, "Đã lưu ảnh hàng hóa.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        messages.error(
            request,
            " ".join(error for errors in form.errors.values() for error in errors)
            or "Chọn ảnh để tải lên.",
        )
    return redirect("product_detail", pk=pk)


@login_required
@require_POST
def receipt_attachment_add(request, pk):
    doc = get_object_or_404(documents_for(request.user), pk=pk)
    if not may_attach(doc, request.user):
        raise PermissionDenied
    form = ReceiptAttachmentForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            add_receipt_attachment(
                doc,
                request.user,
                form.validated_file,
                form.cleaned_data["file"].name,
                **{k: form.cleaned_data[k] for k in form.Meta.fields},
            )
            messages.success(
                request,
                "Đã lưu hồ sơ vào đúng đợt nhập. Tệp gốc giữ nguyên; không thay đổi tồn kho.",
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        messages.error(
            request,
            " ".join(error for errors in form.errors.values() for error in errors),
        )
    return redirect("document_detail", pk=pk)


@login_required
@require_POST
def receipt_attachment_void(request, pk):
    with transaction.atomic():
        attachment = get_object_or_404(
            ReceiptAttachment.objects.select_for_update(),
            pk=pk,
            document__in=documents_for(request.user),
        )
        if not may_attach(attachment.document, request.user):
            raise PermissionDenied
        reason = request.POST.get("reason", "").strip()
        if not reason or len(reason) > 250:
            messages.error(request, "Ghi lý do từ 1 đến 250 ký tự.")
        elif attachment.voided_at:
            messages.error(request, "Hồ sơ đã được đánh dấu; lịch sử không bị ghi đè.")
        else:
            attachment.void_reason, attachment.voided_by, attachment.voided_at = (
                reason,
                request.user,
                timezone.now(),
            )
            attachment.save(update_fields=["void_reason", "voided_by", "voided_at"])
            from .services import audit_document

            audit_document(
                attachment.document,
                request.user,
                "FILE_VOID",
                {
                    "attachment": {
                        "id": attachment.pk,
                        "filename": attachment.filename,
                        "reason": reason,
                    }
                },
            )
            messages.success(
                request,
                "Đã đánh dấu tệp không sử dụng; vẫn giữ bản gốc và lý do trong hồ sơ.",
            )
    return redirect("document_detail", pk=attachment.document_id)


@login_required
def private_file(request, pk):
    # Check linkage and warehouse permissions before selecting the large binary column.
    photo = ProductPhoto.objects.filter(file_id=pk).first()
    attachment = ReceiptAttachment.objects.filter(
        file_id=pk, document__in=documents_for(request.user)
    ).first()
    if not photo and not attachment:
        from django.http import Http404

        raise Http404
    file = get_object_or_404(StoredFile, pk=pk)
    try:
        if file.provider == "drive":
            from .drive import download

            content = download(file)
        else:
            content = bytes(file.data or b"")
    except ValidationError as exc:
        return HttpResponse(
            " ".join(exc.messages), status=503, content_type="text/plain; charset=utf-8"
        )
    response = FileResponse(
        BytesIO(content),
        content_type=file.content_type,
        as_attachment=not bool(photo),
        filename="product-photo.jpg" if photo else attachment.filename,
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response
