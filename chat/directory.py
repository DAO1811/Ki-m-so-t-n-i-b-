"""Read-only company directory. Never exposes contacts or groups outside chat grants."""

import unicodedata

from django.db import connection
from django.db.models import Count, F, Func, Q, Value
from django.db.models.functions import Concat, Lower
from django.urls import reverse

from . import access
from .models import Room


def normalize(value):
    return "".join(
        c
        for c in unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
        if not unicodedata.combining(c)
    )


ACCENTS = "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ"


def folded(expression):
    return Func(
        Lower(expression),
        Value(ACCENTS),
        Value(normalize(ACCENTS)),
        function="TRANSLATE",
    )


def page_params(params):
    offset, limit = int(params.get("offset", 0)), int(params.get("limit", 60))
    if not 0 <= offset <= 100000 or not 1 <= limit <= 100:
        raise ValueError
    field = params.get("field", "all")
    if field not in {"all", "name", "username", "job_title"}:
        raise ValueError
    return offset, limit, field, normalize(params.get("q", "")[:100].strip()).split()


def directory(user, params):
    access.require_use(user)
    offset, limit, field, terms = page_params(params)
    users = (
        access.eligible_users().exclude(pk=user.pk).select_related("function_access")
    )
    expressions = {
        "name": Concat("first_name", Value(" "), "last_name"),
        "username": F("username"),
        "job_title": F("function_access__job_title"),
    }
    if connection.vendor == "postgresql":
        users = users.annotate(
            **{f"directory_{k}": folded(v) for k, v in expressions.items()}
        )
        for term in terms:
            condition = Q()
            for key in expressions if field == "all" else [field]:
                condition |= Q(**{f"directory_{key}__contains": term})
            users = users.filter(condition)
        users = users.order_by("directory_name", "username", "pk")
        rows = list(users[offset : offset + limit + 1])
    else:
        # SQLite development environments have no TRANSLATE. Keep the same semantics.
        def matches(person):
            values = {
                "name": person.get_full_name(),
                "username": person.username,
                "job_title": getattr(
                    getattr(person, "function_access", None), "job_title", ""
                ),
            }
            target = normalize(
                " ".join(values.values()) if field == "all" else values[field]
            )
            return all(term in target for term in terms)

        rows = sorted(
            (u for u in users if matches(u)),
            key=lambda u: (normalize(u.get_full_name()), u.username, u.pk),
        )
        rows = rows[offset : offset + limit + 1]
    return {
        "people": [
            {
                "id": u.pk,
                "name": access.name(u),
                "username": u.username,
                "job_title": getattr(
                    getattr(u, "function_access", None), "job_title", ""
                ),
            }
            for u in rows[:limit]
        ],
        "next_offset": offset + limit if len(rows) > limit else None,
    }


def groups(user, params):
    access.require_use(user)
    offset, limit, _, terms = page_params(params)
    rooms = Room.objects.filter(kind="GROUP", members__user=user, members__active=True)
    # Use a separate count relation: the actor membership filter must not reduce the count.
    rooms = Room.objects.filter(pk__in=rooms.values("pk")).annotate(
        member_count=Count("members", filter=Q(members__active=True)),
    )
    if connection.vendor == "postgresql":
        rooms = rooms.annotate(directory_title=folded(F("title")))
        for term in terms:
            rooms = rooms.filter(directory_title__contains=term)
        rows = list(
            rooms.order_by("directory_title", "pk")[offset : offset + limit + 1]
        )
    else:
        rows = sorted(
            (r for r in rooms if all(t in normalize(r.title) for t in terms)),
            key=lambda r: (normalize(r.title), r.pk),
        )
        rows = rows[offset : offset + limit + 1]
    return {
        "groups": [
            {
                "id": str(r.pk),
                "title": r.title,
                "member_count": r.member_count,
                "owner_id": r.owner_id,
                "url": reverse("chat_room", args=[r.pk]),
            }
            for r in rows[:limit]
        ],
        "next_offset": offset + limit if len(rows) > limit else None,
    }
