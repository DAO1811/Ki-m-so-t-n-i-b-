"""Snapshot previously assigned rights once; new accounts start with no functions."""

from django.conf import settings
from django.db import migrations


def preserve_assigned_access(apps, schema_editor):
    User = apps.get_model(*settings.AUTH_USER_MODEL.split("."))
    Warehouse = apps.get_model("inventory", "Warehouse")
    Access = apps.get_model("inventory", "FunctionAccess")
    db = schema_editor.connection.alias
    modules = [
        "receipts",
        "issues",
        "transfers",
        "loans",
        "returns",
        "stocktakes",
        "adjustments",
    ]
    for user in (
        User.objects.using(db).filter(is_superuser=False).iterator(chunk_size=500)
    ):
        direct = set(
            user.user_permissions.filter(
                content_type__app_label="inventory"
            ).values_list("codename", flat=True)
        )
        previous = direct | set(
            user.groups.filter(
                permissions__content_type__app_label="inventory"
            ).values_list("permissions__codename", flat=True)
        )
        grants = set()
        if "view_document" in previous:
            grants.update([module + "_view" for module in modules])
            grants.update(
                [
                    "dashboard_view",
                    "documents_view",
                    "stock_view",
                    "ledger_view",
                    "reports_view",
                    "tools_export",
                    "files_view",
                ]
            )
        for old, new in [
            ("view_product", "products_view"),
            ("add_product", "products_create"),
            ("change_product", "products_edit"),
            ("view_warehouse", "warehouses_view"),
            ("add_warehouse", "warehouses_create"),
            ("change_warehouse", "warehouses_edit"),
            ("add_customfield", "custom_fields_manage"),
        ]:
            if old in previous:
                grants.add(new)
        if "view_product" in previous:
            grants.add("tools_qr")
        if "add_document" in previous:
            grants.update([module + "_create" for module in modules])
            grants.update(["tools_import", "files_upload", "files_void"])
        if Warehouse.objects.using(db).filter(managers=user).exists():
            grants.update(
                [
                    "receipts_approve",
                    "transfers_receive",
                    "loans_receive",
                    "returns_receive",
                ]
            )
        if Warehouse.objects.using(db).filter(issue_approvers=user).exists():
            grants.update(
                [
                    "issues_approve",
                    "transfers_approve",
                    "loans_approve",
                    "returns_approve",
                ]
            )
        if "approve_inventory_adjustment" in direct:
            grants.add("adjustments_approve")
        while True:
            before = set(grants)
            for code in list(grants):
                module, action = code.rsplit("_", 1)
                if (
                    module in modules + ["products", "warehouses", "files"]
                    and action != "view"
                ):
                    grants.add(module + "_view")
            if grants.intersection({module + "_create" for module in modules}):
                grants.add("products_view")
            if "stocktakes_view" in grants:
                grants.add("products_view")
            if "stocktakes_create" in grants:
                grants.add("adjustments_view")
            if "adjustments_approve" in grants:
                grants.update(["stocktakes_view", "adjustments_view", "documents_view"])
            if grants.intersection({"files_view", "files_upload", "files_void"}):
                grants.add("receipts_view")
            if "returns_create" in grants:
                grants.add("loans_view")
            if grants == before:
                break
        Access.objects.using(db).get_or_create(
            user_id=user.pk, defaults={"permissions": sorted(grants)}
        )


class Migration(migrations.Migration):
    dependencies = [("inventory", "0015_function_access")]
    operations = [
        migrations.RunPython(preserve_assigned_access, migrations.RunPython.noop)
    ]
