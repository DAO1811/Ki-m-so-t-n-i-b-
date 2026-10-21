"""Compatibility exports for existing URLs and integrations.

Warehouse views live in focused modules; company account views live in core.
Import concrete modules in new code. Retain these names during the transition.
"""

from django.utils import timezone as timezone

from core.exporting import export_csv as export_csv
from core.pages import module_placeholder as module_placeholder
from core.views import employee_form as employee_form
from core.views import password_change as password_change
from core.views import require_admin as require_admin
from core.views import team as team

from .catalog import custom_fields as custom_fields
from .catalog import product_edit as product_edit
from .catalog import product_new as product_new
from .catalog import products as products
from .common import balances as balances
from .common import date_range as date_range
from .common import request_balances as request_balances
from .dashboard import dashboard as dashboard
from .document_detail import document_close as document_close
from .document_detail import document_detail as document_detail
from .document_detail import document_post as document_post
from .document_editing import document_edit as document_edit
from .document_editing import document_form_response as document_form_response
from .document_editing import document_new as document_new
from .document_editing import validate_available_lines as validate_available_lines
from .document_list import approvals as approvals
from .document_list import documents as documents
from .imports import loans as loans
from .imports import receipt_import as receipt_import
from .imports import receipt_template as receipt_template
from .stock import availability as availability
from .stock import ledger as ledger
from .stock import reports as reports
from .stock import stock as stock
from .warehouses import warehouse_edit as warehouse_edit
from .warehouses import warehouse_form as warehouse_form
from .warehouses import warehouse_list as warehouse_list
from .warehouses import warehouse_new as warehouse_new
from .warehouses import warehouse_scope as warehouse_scope
