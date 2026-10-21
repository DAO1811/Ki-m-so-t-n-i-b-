from django.contrib.auth.decorators import login_required
from django.http import HttpResponse


@login_required
def receipt_template(request):
    from ..excel import receipt_template

    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = (
        'attachment; filename="mau-nhap-kho-theo-kho.xlsx"'
    )
    receipt_template(user=request.user).save(response)
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
def receipt_import(request):
    from ..receipt_import_views import receipt_import as import_receipts

    return import_receipts(request)


@login_required
def loans(request):
    from ..loan_views import loan_dashboard

    return loan_dashboard(request)
