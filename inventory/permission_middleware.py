"""Fail-closed authorization for company views, alternate URLs and APIs."""

from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin

from .access import (
    APPROVE_KEYS,
    CREATE_KEYS,
    KIND_MODULES,
    approval_key,
    function_codes,
    is_admin,
)

VIEW_KEYS = {
    "products": "products_view",
    "product_detail": "products_view",
    "qr_landing": "products_view",
    "product_new": "products_create",
    "product_import": "products_create",
    "product_import_template": "products_create",
    "product_edit": "products_edit",
    "product_photo_add": "products_edit",
    "product_qr": "tools_qr",
    "product_labels": "tools_qr",
    "warehouse_list": "warehouses_view",
    "warehouse_new": "warehouses_create",
    "warehouse_edit": "warehouses_edit",
    "documents": "documents_view",
    "stock": "stock_view",
    "ledger": "ledger_view",
    "reports": "reports_view",
    "receipt_import": "receipts_create",
    "receipt_template": "receipts_create",
    "issue_import": "issues_create",
    "issue_template": "issues_create",
    "custom_fields": "custom_fields_manage",
    "team": "team_view",
    "stocktakes": "stocktakes_view",
    "stocktake_detail": "stocktakes_view",
    "stocktake_lookup": "stocktakes_view",
    "stocktake_report": "stocktakes_view",
    "stocktake_count": "stocktakes_create",
    "stocktake_begin": "stocktakes_create",
    "stocktake_paper": "stocktakes_create",
    "stocktake_submit": "stocktakes_create",
    "stocktake_cancel": "stocktakes_create",
    "loan_return": "returns_create",
    "loan_return_edit": "returns_create",
}
ADMIN_VIEWS = {
    "storage_settings",
    "storage_measure",
    "storage_download",
    "storage_drive_usage",
    "storage_export",
    "employee_new",
    "employee_edit",
    "drive_settings",
    "drive_connect",
    "drive_callback",
    "drive_picker_token",
    "drive_folder",
    "drive_check",
}


class FunctionAccessMiddleware(MiddlewareMixin):
    def process_view(self, request, view, args, kwargs):
        if (
            not view.__module__.startswith(
                ("inventory.", "core.", "workflows.", "people.", "deviations.")
            )
            or not request.user.is_authenticated
        ):
            return None
        if is_admin(request.user):
            return None
        name = request.resolver_match.url_name
        codes = function_codes(request.user)
        allowed = False
        if view.__module__.startswith("deviations."):
            from deviations.access import route_allowed

            allowed = route_allowed(request.user, name, request.method)
        elif name in {"processes", "human_resources"}:
            allowed = request.method in {"GET", "HEAD"}
        elif name in {"dashboard", "password_change", "warehouse_scope"}:
            allowed = True
        elif name in ADMIN_VIEWS:
            allowed = False
        elif name in VIEW_KEYS:
            allowed = VIEW_KEYS[name] in codes
            if name == "documents" and request.GET.get("kind") in KIND_MODULES:
                allowed = (
                    allowed or KIND_MODULES[request.GET["kind"]] + "_view" in codes
                )
            if name == "stocktakes" and request.method == "POST":
                allowed = "stocktakes_create" in codes
        elif name in {"operation_new", "document_new"}:
            kind = kwargs.get(
                "kind", request.POST.get("kind", request.GET.get("kind", "IN"))
            ).upper()
            allowed = KIND_MODULES.get(kind, "") + "_create" in codes
        elif name in {
            "document_detail",
            "document_edit",
            "document_post",
            "document_close",
            "receipt_attachment_add",
        }:
            from .models import Document

            doc = Document.objects.filter(pk=kwargs["pk"]).first()
            if doc is None:
                return None
            allowed = KIND_MODULES.get(doc.kind, "") + "_view" in codes
            if name == "document_edit" or (
                name == "document_close"
                and kwargs.get("action", "").upper() == "CANCEL"
            ):
                allowed = (
                    allowed and KIND_MODULES.get(doc.kind, "") + "_create" in codes
                )
            elif name in {"document_post", "document_close"}:
                allowed = allowed and approval_key(doc) in codes
            elif name == "receipt_attachment_add":
                allowed = allowed and "files_upload" in codes
        elif name == "receipt_attachment_void":
            allowed = "files_void" in codes and "receipts_view" in codes
        elif name == "private_file":
            allowed = bool(codes & {"products_view", "files_view"})
        elif name == "availability":
            allowed = bool(codes & (CREATE_KEYS | {"stock_view"}))
        elif name == "loans":
            allowed = bool(codes & {"loans_view", "returns_view"})
        elif name == "approvals":
            allowed = bool(codes & APPROVE_KEYS)
        if request.GET.get("export") and name in {"documents", "stock", "ledger"}:
            allowed = allowed and "tools_export" in codes
        if not allowed:
            raise PermissionDenied(
                "Bạn chưa được admin cấp quyền cho mục hoặc thao tác này."
            )
