from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import ProductForm
from ..models import (
    CustomField,
    Product,
)
from ..services import documents_for


@login_required
def products(request):
    from django.db.models import Prefetch

    from ..models import ProductPhoto

    qs = (
        Product.objects.all()
        .order_by("sku")
        .prefetch_related(
            Prefetch(
                "photos",
                queryset=ProductPhoto.objects.order_by("pk"),
                to_attr="catalog_photos",
            )
        )
    )
    import_result = None
    if request.GET.get("batch"):
        result = request.session.get("product_import_result", {})
        if (
            result.get("owner") == request.user.pk
            and result.get("key") == request.GET["batch"]
        ):
            import_result = dict(result)
            import_result["documents"] = list(
                documents_for(request.user)
                .filter(pk__in=result.get("document_ids", []))
                .select_related("destination")
                .order_by("pk")[:20]
            )
            import_result["document_count"] = len(result.get("document_ids", []))
            qs = qs.filter(pk__in=result["ids"])
        else:
            messages.info(
                request,
                "Lượt nhập này không còn trong phiên làm việc. Đang hiển thị toàn bộ hàng hóa.",
            )
    if request.GET.get("q"):
        qs = qs.filter(
            Q(name__icontains=request.GET["q"])
            | Q(sku__icontains=request.GET["q"])
            | Q(category__icontains=request.GET["q"])
            | Q(brand__icontains=request.GET["q"])
            | Q(model_number__icontains=request.GET["q"])
        )
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "products.html",
        {"products": page, "page_obj": page, "import_result": import_result},
    )


@login_required
def product_new(request):
    form = ProductForm(request.POST or None)
    from ..forms import ProductPhotoForm
    from ..media import add_product_photo

    photo_form = ProductPhotoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid() and photo_form.is_valid():
        try:
            with transaction.atomic():
                product = form.save()
                if photo_form.cleaned_data.get("image"):
                    add_product_photo(
                        product,
                        request.user,
                        photo_form.validated_image,
                        photo_form.cleaned_data["caption"],
                    )
            messages.success(request, "Đã thêm hàng hóa và tạo mã QR.")
            return redirect("product_detail", pk=product.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(
        request, "product_form.html", {"form": form, "photo_form": photo_form}
    )


@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    from ..forms import ProductPhotoForm
    from ..media import add_product_photo

    photo_form = ProductPhotoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid() and photo_form.is_valid():
        try:
            with transaction.atomic():
                product = form.save()
                if photo_form.cleaned_data.get("image"):
                    add_product_photo(
                        product,
                        request.user,
                        photo_form.validated_image,
                        photo_form.cleaned_data["caption"],
                    )
            messages.success(request, "Đã cập nhật hàng hóa.")
            return redirect("product_detail", pk=product.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(
        request,
        "product_form.html",
        {
            "form": form,
            "editing": True,
            "photo_form": photo_form,
            "photos": product.photos.select_related("file"),
        },
    )


@login_required
def custom_fields(request):
    from ..forms import CustomFieldForm

    editing = None
    field_id = (
        request.POST.get("field_id")
        if request.method == "POST"
        else request.GET.get("edit")
    )
    if field_id:
        editing = get_object_or_404(
            CustomField,
            pk=field_id if str(field_id).isdigit() and len(str(field_id)) <= 18 else 0,
        )
    form = CustomFieldForm(request.POST or None, instance=editing)
    if request.method == "POST" and form.is_valid():
        saved = form.save()
        messages.success(
            request,
            "Đã đổi tên thông tin; dữ liệu hàng hóa được giữ nguyên."
            if editing
            else f"Đã thêm ô {saved.label}. Mở Thêm / Sửa hàng hóa để nhập giá trị cho từng mã.",
        )
        return redirect("custom_fields")
    return render(
        request,
        "custom_fields.html",
        {
            "form": form,
            "fields": CustomField.objects.order_by("id"),
            "editing": editing,
        },
    )
