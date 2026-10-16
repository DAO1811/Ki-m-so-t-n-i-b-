from django.urls import path
from . import views

urlpatterns = [
    path("import/receipt/", views.receipt_import, name="receipt_import"),
    path("import/receipt/template/", views.receipt_template, name="receipt_template"),
    path("", views.dashboard, name="dashboard"),
    path("documents/", views.documents, name="documents"),
    path("documents/new/", views.document_new, name="document_new"),
    path("documents/<int:pk>/edit/", views.document_edit, name="document_edit"),
    path("documents/<int:pk>/", views.document_detail, name="document_detail"),
    path("documents/<int:pk>/post/", views.document_post, name="document_post"),
    path("stock/", views.stock, name="stock"),
    path("ledger/", views.ledger, name="ledger"),
    path("loans/", views.loans, name="loans"),
    path("products/", views.products, name="products"),
    path("products/new/", views.product_new, name="product_new"),
]
