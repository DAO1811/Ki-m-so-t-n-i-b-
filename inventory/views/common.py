from datetime import date

from django.contrib import messages
from django.utils import timezone

from ..models import Balance
from ..services import warehouses_for
from ..workspace import selected_warehouse


def balances(user):
    return Balance.objects.filter(warehouse__in=warehouses_for(user)).select_related(
        "warehouse", "product"
    )


def request_balances(request):
    qs = balances(request.user)
    warehouse = selected_warehouse(request)
    return qs.filter(warehouse=warehouse) if warehouse else qs


def date_range(request):
    today = timezone.localdate()
    try:
        start = date.fromisoformat(request.GET.get("from", str(today.replace(day=1))))
        end = date.fromisoformat(request.GET.get("to", str(today)))
        if start > end or (end - start).days > 366:
            raise ValueError
    except (ValueError, TypeError):
        start, end = today.replace(day=1), today
        messages.error(
            request,
            "Khoảng ngày không hợp lệ. Đang hiển thị tháng hiện tại; tối đa 366 ngày mỗi lần.",
        )
    return start, end
