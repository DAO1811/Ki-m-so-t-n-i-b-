from django.urls import path

from . import drive_views, views
from . import records_views as records
from . import stocktake_views as counts

urlpatterns = [
    path("products/labels/", records.product_labels, name="product_labels"),
    path("products/<int:pk>/", records.product_detail, name="product_detail"),
    path("products/<int:pk>/qr.png", records.product_qr, name="product_qr"),
    path(
        "products/<int:pk>/photos/", records.product_photo_add, name="product_photo_add"
    ),
    path("q/items/<uuid:token>/", records.qr_landing, name="qr_landing"),
    path("files/<uuid:pk>/", records.private_file, name="private_file"),
    path(
        "documents/<int:pk>/attachments/",
        records.receipt_attachment_add,
        name="receipt_attachment_add",
    ),
    path(
        "attachments/<int:pk>/void/",
        records.receipt_attachment_void,
        name="receipt_attachment_void",
    ),
    path("stocktakes/", counts.stocktakes, name="stocktakes"),
    path("stocktakes/<int:pk>/", counts.stocktake_detail, name="stocktake_detail"),
    path(
        "stocktakes/<int:pk>/lookup/", counts.stocktake_lookup, name="stocktake_lookup"
    ),
    path("stocktakes/<int:pk>/count/", counts.stocktake_count, name="stocktake_count"),
    path(
        "stocktakes/<int:pk>/submit/", counts.stocktake_submit, name="stocktake_submit"
    ),
    path(
        "stocktakes/<int:pk>/cancel/", counts.stocktake_cancel, name="stocktake_cancel"
    ),
    path(
        "stocktakes/<int:pk>/report/", counts.stocktake_report, name="stocktake_report"
    ),
    path("settings/drive/", drive_views.drive_settings, name="drive_settings"),
    path("settings/drive/connect/", drive_views.drive_connect, name="drive_connect"),
    path("settings/drive/callback/", drive_views.drive_callback, name="drive_callback"),
    path(
        "settings/drive/picker-token/",
        drive_views.drive_picker_token,
        name="drive_picker_token",
    ),
    path("settings/drive/folder/", drive_views.drive_folder, name="drive_folder"),
    path("settings/drive/check/", drive_views.drive_check, name="drive_check"),
    path("workspace/warehouse/", views.warehouse_scope, name="warehouse_scope"),
    path("api/availability/", views.availability, name="availability"),
    path("operations/<str:kind>/", views.document_new, name="operation_new"),
    path("approvals/", views.approvals, name="approvals"),
    path("warehouses/", views.warehouse_list, name="warehouse_list"),
    path("warehouses/new/", views.warehouse_new, name="warehouse_new"),
    path("warehouses/<int:pk>/edit/", views.warehouse_edit, name="warehouse_edit"),
    path("team/", views.team, name="team"),
    path("team/new/", views.employee_form, name="employee_new"),
    path("team/<int:pk>/edit/", views.employee_form, name="employee_edit"),
    path("account/password/", views.password_change, name="password_change"),
    path("reports/", views.reports, name="reports"),
    path("custom-fields/", views.custom_fields, name="custom_fields"),
    path("products/<int:pk>/edit/", views.product_edit, name="product_edit"),
    path("import/receipt/", views.receipt_import, name="receipt_import"),
    path("import/receipt/template/", views.receipt_template, name="receipt_template"),
    path("", views.dashboard, name="dashboard"),
    path("documents/", views.documents, name="documents"),
    path("documents/new/", views.document_new, name="document_new"),
    path("documents/<int:pk>/edit/", views.document_edit, name="document_edit"),
    path("documents/<int:pk>/", views.document_detail, name="document_detail"),
    path("documents/<int:pk>/post/", views.document_post, name="document_post"),
    path(
        "documents/<int:pk>/close/<str:action>/",
        views.document_close,
        name="document_close",
    ),
    path("stock/", views.stock, name="stock"),
    path("ledger/", views.ledger, name="ledger"),
    path("loans/", views.loans, name="loans"),
    path("products/", views.products, name="products"),
    path("products/new/", views.product_new, name="product_new"),
]
