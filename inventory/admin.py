from django.contrib import admin
from .models import Warehouse, Product, CustomField
from .forms import ProductForm


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ["code", "name", "address"]
    filter_horizontal = ["members", "managers", "issue_approvers"]
    search_fields = ["code", "name"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductForm
    list_display = ["sku", "name", "unit", "minimum"]
    search_fields = ["sku", "name"]


admin.site.register(CustomField)
# Ledger, balances and posted documents are intentionally not editable in admin.
