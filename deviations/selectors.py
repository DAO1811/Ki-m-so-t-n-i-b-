"""Read-only queries, deliberately independent of the global warehouse filter."""

from django.db.models import Count, F, Min, Q
from django.utils import timezone

from .constants import TERMINAL, ActionStatus
from .models import Case


def cases():
    return (
        Case.objects.select_related("category", "created_by", "owner", "duplicate_of")
        .annotate(
            next_due=Min(
                "actions__due_date",
                filter=Q(actions__round=F("round"))
                & ~Q(actions__status=ActionStatus.DONE),
            )
        )
        .order_by("-pk")
    )


def filtered_cases(user, params):
    qs = cases()
    term = params.get("q", "").strip()[:200]
    if term:
        query = (
            Q(title__icontains=term)
            | Q(department__icontains=term)
            | Q(actual__icontains=term)
        )
        raw = term.rsplit("-", 1)[-1]
        if raw.isascii() and raw.isdigit() and len(raw) <= 18:
            query |= Q(pk=int(raw))
        qs = qs.filter(query)
    for key in ("status", "severity"):
        if params.get(key):
            qs = qs.filter(**{key: params[key][:16]})
    raw_category = params.get("category", "")
    if raw_category.isascii() and raw_category.isdigit() and len(raw_category) <= 18:
        qs = qs.filter(category_id=int(raw_category))
    tab = params.get("tab", "all")
    if tab == "mine":
        qs = qs.filter(created_by=user)
    elif tab == "assigned":
        qs = qs.filter(Q(owner=user) | Q(actions__assignee=user)).distinct()
    elif tab == "overdue":
        qs = qs.filter(next_due__lt=timezone.localdate()).exclude(status__in=TERMINAL)
    elif tab == "closed":
        qs = qs.filter(status="CLOSED")
    return qs


def metrics():
    qs = cases()
    return {
        "total": qs.count(),
        "reported": qs.filter(status="REPORTED").count(),
        "active": qs.exclude(status__in=TERMINAL).count(),
        "overdue": qs.filter(next_due__lt=timezone.localdate())
        .exclude(status__in=TERMINAL)
        .count(),
        "closed": qs.filter(status="CLOSED").count(),
    }


def category_report():
    return (
        Case.objects.values("category__name")
        .annotate(total=Count("pk"), closed=Count("pk", filter=Q(status="CLOSED")))
        .order_by("category__name")
    )
