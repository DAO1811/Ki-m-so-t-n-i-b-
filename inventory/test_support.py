"""Explicit function grants for pre-existing regression fixtures, never production setup."""

from .access import normalize_permissions, FUNCTION_KEYS
from .models import FunctionAccess


OPERATOR = {
    "dashboard_view",
    "products_view",
    "warehouses_view",
    "documents_view",
    "stock_view",
    "ledger_view",
    "reports_view",
    "tools_import",
    "tools_export",
    "tools_qr",
    "files_upload",
    "files_void",
} | {
    module + "_create"
    for module in [
        "receipts",
        "issues",
        "transfers",
        "loans",
        "returns",
        "stocktakes",
        "adjustments",
    ]
}
MANAGER = set(FUNCTION_KEYS) - {
    "warehouses_create",
    "warehouses_edit",
    "custom_fields_manage",
    "team_view",
    "adjustments_approve",
}


def grant_functions(user, codes):
    FunctionAccess.objects.update_or_create(
        user=user, defaults={"permissions": normalize_permissions(codes)}
    )
