"""Shared warehouse scope and presentation context for the workspace."""

from django.db.models import Q
from django.http import Http404

from .access import access_context
from .services import can_approve_adjustments, documents_for, warehouses_for


def selected_warehouse(request):
    if not request.user.is_authenticated:
        return None
    if hasattr(request, "_warehouse_scope_cache"):
        return request._warehouse_scope_cache
    raw = request.GET.get("warehouse", request.session.get("warehouse_scope", ""))
    if not raw:
        if "warehouse" in request.GET:
            request.session.pop("warehouse_scope", None)
        request._warehouse_scope_cache = None
        return None
    if not str(raw).isdigit() or len(str(raw)) > 18:
        raise Http404("Kho không hợp lệ.")
    warehouse = warehouses_for(request.user).filter(pk=raw).first()
    if warehouse is None:
        if "warehouse" in request.GET:
            raise Http404("Kho nằm ngoài phạm vi truy cập.")
        request.session.pop("warehouse_scope", None)
    if "warehouse" in request.GET and warehouse is not None:
        request.session["warehouse_scope"] = str(warehouse.pk)
    request._warehouse_scope_cache = warehouse
    return warehouse


def scoped_documents(request):
    qs = documents_for(request.user)
    warehouse = selected_warehouse(request)
    return (
        qs.filter(Q(source=warehouse) | Q(destination=warehouse)) if warehouse else qs
    )


def workspace_context(request):
    if not request.user.is_authenticated:
        return {}
    name = request.resolver_match.url_name if request.resolver_match else ""
    labels = {
        "dashboard": "Tổng quan",
        "documents": "Quản lý phiếu",
        "document_new": "Lập phiếu",
        "operation_new": "Lập phiếu",
        "document_edit": "Sửa phiếu",
        "document_detail": "Chi tiết phiếu",
        "stock": "Tồn kho",
        "ledger": "Thẻ kho",
        "loans": "Mượn & trả",
        "loan_return": "Trả hàng theo lệnh mượn",
        "loan_return_edit": "Sửa phiếu trả hàng",
        "products": "Danh mục hàng hóa",
        "product_new": "Thêm hàng hóa",
        "product_import": "Thêm hàng hóa từ Excel",
        "product_edit": "Sửa hàng hóa",
        "product_detail": "Hồ sơ hàng hóa",
        "product_labels": "In tem QR",
        "stocktakes": "Kiểm kê theo kho",
        "stocktake_detail": "Biên bản kiểm kê",
        "stocktake_paper": "Nhập kết quả kiểm kê giấy",
        "stocktake_report": "Biên bản kiểm kê",
        "drive_settings": "Google Drive",
        "approvals": "Duyệt phiếu",
        "warehouse_list": "Kho hàng",
        "warehouse_edit": "Sửa kho",
        "warehouse_new": "Thêm kho",
        "team": "Nhân viên & phân quyền",
        "employee_new": "Thêm nhân viên",
        "employee_edit": "Sửa nhân viên",
        "reports": "Báo cáo",
        "receipt_import": "Nhập kho từ Excel",
        "issue_import": "Xuất kho từ Excel",
        "custom_fields": "Trường bổ sung",
    }
    try:
        active = selected_warehouse(request)
    except Http404:
        active = None
    from .navigation import navigation

    access = access_context(request.user)
    return {
        "workspace_warehouses": warehouses_for(request.user).order_by("code"),
        "active_warehouse": active,
        "page_name": labels.get(name, "Quản lý kho"),
        "can_approve_inventory_adjustments": can_approve_adjustments(request.user),
        "access": access,
        "navigation": navigation(request, access),
        "route_name": name,
        "operation_kind": request.resolver_match.kwargs.get("kind", "").upper()
        if request.resolver_match
        else "",
    }
