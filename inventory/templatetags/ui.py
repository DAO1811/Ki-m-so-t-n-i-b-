from decimal import Decimal, InvalidOperation

from django import template
from django.utils.safestring import mark_safe

register = template.Library()
ICONS = {
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
    "box": '<path d="m3 7 9-4 9 4-9 4-9-4Zm0 0v10l9 4 9-4V7M12 11v10M7 5l10 4"/>',
    "warehouse": '<path d="M3 21V8l9-5 9 5v13M3 21h18M7 21V11h10v10M7 15h10M7 18h10"/>',
    "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M22 21v-2a4 4 0 0 0-3-3.87"/><circle cx="9" cy="7" r="4"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>',
    "in": '<path d="M12 3v12m-5-5 5 5 5-5M4 15v5h16v-5"/>',
    "out": '<path d="M12 16V4m-5 5 5-5 5 5M4 15v5h16v-5"/>',
    "transfer": '<path d="M4 7h16m-4-4 4 4-4 4M20 17H4m4-4-4 4 4 4"/>',
    "loan": '<path d="M3 8h11m-4-4 4 4-4 4M21 16H10m4-4-4 4 4 4M3 15v5h4M21 9V4h-4"/>',
    "file": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Zm0 0v6h6M8 13h8M8 17h5"/>',
    "check": '<path d="m5 12 4 4L19 6"/>',
    "shield": '<path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z"/><path d="m8 12 3 3 5-6"/>',
    "chart": '<path d="M3 3v18h18M7 14l4-5 4 3 6-7"/>',
    "history": '<path d="M3 11a9 9 0 1 1 2 7M3 4v7h7M12 7v5l3 2"/>',
    "count": '<rect x="5" y="4" width="14" height="18" rx="2"/><path d="M9 2h6v4H9zM9 12l2 2 4-4M9 18h6"/>',
    "settings": '<path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="3"/><circle cx="15" cy="17" r="3"/>',
    "menu": '<path d="M4 6h16M4 12h16M4 18h16"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "arrow": '<path d="M5 12h14m-5-5 5 5-5 5"/>',
    "chevron": '<path d="m9 5 7 7-7 7"/>',
    "download": '<path d="M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5"/>',
    "upload": '<path d="M12 16V4m-4 4 4-4 4 4M4 16v5h16v-5"/>',
    "alert": '<path d="m12 3 10 18H2L12 3ZM12 9v4M12 17h.01"/>',
    "bell": '<path d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4"/>',
    "moon": '<path d="M21 13A9 9 0 0 1 11 3a9 9 0 1 0 10 10Z"/>',
    "refresh": '<path d="M20 7a9 9 0 1 0 1 8M20 2v5h-5"/>',
    "logout": '<path d="M9 4H4v16h5M9 12h12m-4-4 4 4-4 4"/>',
    "lock": '<rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/>',
    "edit": '<path d="m16 3 5 5-12 12-6 1 1-6L16 3ZM13 6l5 5"/>',
    "trash": '<path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7"/>',
    "home": '<path d="m3 10 9-7 9 7M5 9v12h5v-7h4v7h5V9"/>',
    "money": '<rect x="2" y="5" width="20" height="14" rx="2"/><circle cx="12" cy="12" r="3"/><path d="M5 9v6M19 9v6"/>',
    "empty": '<path d="m3 8 4-5h10l4 5v12H3V8ZM3 8h5l2 4h4l2-4h5"/>',
}


@register.simple_tag
def icon(name):
    return mark_safe(
        '<svg class="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
        + ICONS.get(name, ICONS["box"])
        + "</svg>"
    )


@register.filter
def number(value):
    try:
        n = Decimal(str(value))
        s = f"{n:,.3f}".rstrip("0").rstrip(".")
        return s.replace(",", "_").replace(".", ",").replace("_", ".")
    except (InvalidOperation, ValueError, TypeError):
        return "0"


@register.filter
def money(value):
    try:
        return f"{Decimal(str(value)):,.0f}".replace(",", ".") + " ₫"
    except (InvalidOperation, ValueError, TypeError):
        return "0 ₫"


@register.filter
def status_label(value):
    return {
        "DRAFT": "Chờ duyệt",
        "TRANSIT": "Chờ nhận hàng",
        "POSTED": "Hoàn tất",
        "REJECTED": "Yêu cầu sửa",
        "CANCELLED": "Đã hủy",
    }.get(value, value)


@register.simple_tag(takes_context=True)
def query_page(context, page):
    query = context["request"].GET.copy()
    query["page"] = page
    return "?" + query.urlencode()
