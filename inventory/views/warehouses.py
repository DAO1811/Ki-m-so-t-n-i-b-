from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from ..forms import WarehouseForm
from ..services import warehouses_for


@login_required
def warehouse_list(request):
    return render(
        request,
        "warehouses.html",
        {
            "warehouses": warehouses_for(request.user)
            .prefetch_related("members", "managers", "issue_approvers")
            .order_by("code")
        },
    )


@login_required
def warehouse_new(request):
    return warehouse_form(request)


@login_required
def warehouse_edit(request, pk):
    return warehouse_form(
        request, get_object_or_404(warehouses_for(request.user), pk=pk)
    )


def warehouse_form(request, warehouse=None):
    form = WarehouseForm(request.POST or None, instance=warehouse, actor=request.user)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            import json

            from django.contrib.admin.models import ADDITION, CHANGE, LogEntry
            from django.contrib.contenttypes.models import ContentType

            before = {}
            if warehouse:
                locked = (
                    type(warehouse).objects.select_for_update().get(pk=warehouse.pk)
                )
                before = {
                    name: list(getattr(locked, name).values_list("pk", flat=True))
                    for name in ["members", "managers", "issue_approvers"]
                }
            saved = form.save()
            if not warehouse and not request.user.is_superuser:
                saved.members.add(request.user)
            after = {
                name: list(getattr(saved, name).values_list("pk", flat=True))
                for name in ["members", "managers", "issue_approvers"]
            }
            LogEntry.objects.create(
                user=request.user,
                content_type=ContentType.objects.get_for_model(saved),
                object_id=str(saved.pk),
                object_repr=str(saved)[:200],
                action_flag=CHANGE if warehouse else ADDITION,
                change_message="Lưu kho / phân công: "
                + json.dumps({"before": before, "after": after}, ensure_ascii=False),
            )
        messages.success(
            request, "Đã lưu thông tin kho và phân công được phép thay đổi."
        )
        return redirect("warehouse_list")
    return render(
        request, "warehouse_form.html", {"form": form, "editing": bool(warehouse)}
    )


@login_required
@require_POST
def warehouse_scope(request):
    raw = request.POST.get("warehouse", "")
    if raw:
        warehouse = get_object_or_404(
            warehouses_for(request.user),
            pk=raw if raw.isdigit() and len(raw) <= 18 else 0,
        )
        request.session["warehouse_scope"] = str(warehouse.pk)
    else:
        request.session.pop("warehouse_scope", None)
    target = request.POST.get("next", "/")
    if not url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        target = "/"
    return redirect(target)
