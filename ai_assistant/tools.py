"""Read-only, permission-scoped lookups the chat model may request (Trợ lý AI v2).

Owner decision 14/11/2026: data the asking user may already see can be sent to
Groq so the model can answer about it. Every tool re-checks the asker's function
grants and warehouse scope on each call, never writes, and never returns chat
messages, passwords, keys, passkeys or file contents. Results are compact text
with links to the source screen. See docs/AI_ASSISTANT_V2_SPEC.md.
"""

import json
import re
from dataclasses import dataclass, field
from datetime import date, timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import F, Q, Sum
from django.urls import reverse
from django.utils import timezone

from inventory.access import has_function
from inventory.models import (
    Balance,
    LoanHolding,
    Movement,
    Product,
    StocktakeSession,
)
from inventory.services import approval_documents_for, documents_for, warehouses_for

from .data import number
from .guides import GUIDES
from .knowledge import ARTICLES, find_article

MAX_ROWS = 30
MAX_TEXT_BYTES = 3000
MAX_CALLS_PER_QUESTION = 4

KINDS = {
    "IN": "Nhập kho",
    "OUT": "Xuất kho",
    "TRANSFER": "Luân chuyển",
    "LOAN": "Cho mượn",
    "RETURN": "Trả hàng mượn",
    "COUNT": "Kiểm kê",
    "ADJUST": "Điều chỉnh tồn",
}
STATUSES = {
    "DRAFT": "Chờ duyệt",
    "TRANSIT": "Đang chuyển / chờ nhận",
    "POSTED": "Đã ghi sổ",
    "REJECTED": "Yêu cầu sửa",
    "CANCELLED": "Đã hủy",
}


class ToolError(Exception):
    """A user-facing reason the lookup cannot run (sent back to the model)."""


@dataclass
class ToolResult:
    text: str
    rows: int = 0
    sources: list = field(default_factory=list)


def _clip(text):
    data = text.encode()
    if len(data) <= MAX_TEXT_BYTES:
        return text
    return (
        data[:MAX_TEXT_BYTES].decode("utf-8", errors="ignore")
        + "\n… (đã rút gọn; mở màn hình nguồn để xem đủ)"
    )


def _str(args, key, limit=100):
    value = args.get(key)
    if value is None or value == "":
        return ""
    if not isinstance(value, (str, int)):
        raise ToolError(f"Tham số {key} không hợp lệ.")
    value = str(value).strip()
    if len(value) > limit or any(ord(c) < 32 for c in value):
        raise ToolError(f"Tham số {key} không hợp lệ.")
    return value


def _date(args, key):
    value = _str(args, key, 10)
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ToolError(f"{key} phải có dạng YYYY-MM-DD.") from None


def _range(args):
    start, end = _date(args, "date_from"), _date(args, "date_to")
    if start and end and not 0 <= (end - start).days <= 366:
        raise ToolError("Khoảng ngày tối đa 1 năm.")
    return start, end


def _need(user, code, label):
    if not has_function(user, code):
        raise ToolError(f"Người hỏi chưa được cấp quyền {label}; không được tiết lộ.")


def _warehouses(user, args):
    allowed = warehouses_for(user)
    code = _str(args, "warehouse_code", 50)
    if not code:
        return allowed
    picked = allowed.filter(code__iexact=code)
    if not picked.exists():
        raise ToolError(
            f"Kho {code} không tồn tại hoặc nằm ngoài phạm vi người hỏi được xem."
        )
    return picked


def _products(args):
    sku, query = _str(args, "sku", 50), _str(args, "query", 100)
    if sku:
        return Product.objects.filter(sku__iexact=sku)
    if query:
        return Product.objects.filter(
            Q(name__icontains=query) | Q(sku__icontains=query)
        )
    return Product.objects.all()


def _doc_number(args):
    raw = _str(args, "number", 20).upper().removeprefix("PK-").lstrip("#")
    if not raw:
        return None
    if not raw.isdigit() or len(raw) > 12:
        raise ToolError("Số phiếu có dạng PK-000123 hoặc 123.")
    return int(raw)


def _doc_line(d):
    route = (
        " → ".join(w.code for w in (d.source, d.destination) if w is not None) or "—"
    )
    return (
        f"PK-{d.pk:06d} · {KINDS.get(d.kind, d.kind)} · "
        f"{STATUSES.get(d.status, d.status)} · ngày {d.business_date:%d/%m/%Y} · "
        f"kho {route}"
    )


def _doc_source(d):
    return {"label": f"PK-{d.pk:06d}", "url": reverse("document_detail", args=[d.pk])}


# --- tools -----------------------------------------------------------------


def product_search(user, args):
    _need(user, "products_view", "xem danh mục hàng hóa")
    qs = _products(args).order_by("sku")
    total = qs.count()
    rows = list(qs[:MAX_ROWS])
    lines = [
        f"{p.sku} · {p.name} · ĐVT {p.unit} · nhóm {p.category or '—'} · "
        f"định mức {number(p.minimum)}"
        for p in rows
    ]
    head = f"Tìm thấy {total} mã hàng."
    return ToolResult(
        "\n".join([head, *lines]),
        len(rows),
        [
            {"label": p.sku, "url": reverse("product_detail", args=[p.pk])}
            for p in rows[:5]
        ],
    )


def stock(user, args):
    _need(user, "stock_view", "xem tồn kho")
    qs = Balance.objects.filter(
        warehouse__in=_warehouses(user, args), product__in=_products(args)
    )
    flt = _str(args, "filter", 20) or "all"
    if flt == "below_minimum":
        qs = qs.filter(quantity__lt=F("product__minimum"))
    elif flt == "zero":
        qs = qs.filter(quantity=0)
    elif flt != "all":
        raise ToolError("filter chỉ nhận all, below_minimum hoặc zero.")
    else:
        qs = qs.exclude(quantity=0, value=0)
    totals = qs.aggregate(value=Sum("value"))
    rows = list(
        qs.select_related("product", "warehouse").order_by(
            "warehouse__code", "product__sku"
        )[: MAX_ROWS + 1]
    )
    lines = [
        f"Kho {b.warehouse.code} · {b.product.sku} · {b.product.name}: tồn {number(b.quantity)} "
        f"{b.product.unit} · giá trị {number(b.value)} đ · định mức {number(b.product.minimum)}"
        for b in rows[:MAX_ROWS]
    ]
    head = (
        f"{qs.count()} dòng tồn (mỗi dòng là một mã tại một kho), tổng giá trị "
        f"{number(totals['value'])} đ. Không gồm hàng đang chuyển hoặc hàng mượn tạm."
    )
    if len(rows) > MAX_ROWS:
        head += f" Chỉ liệt kê {MAX_ROWS} dòng đầu."
    return ToolResult(
        "\n".join([head, *lines]) if lines else head,
        min(len(rows), MAX_ROWS),
        [{"label": "Tồn kho", "url": reverse("stock")}],
    )


def stock_ledger(user, args):
    _need(user, "ledger_view", "xem thẻ kho")
    start, end = _range(args)
    qs = Movement.objects.filter(
        warehouse__in=_warehouses(user, args), product__in=_products(args)
    )
    if start:
        qs = qs.filter(created_at__date__gte=start)
    if end:
        qs = qs.filter(created_at__date__lte=end)
    rows = list(
        qs.select_related("document", "product", "warehouse").order_by(
            "-created_at", "-pk"
        )[:MAX_ROWS]
    )
    lines = [
        f"{timezone.localtime(m.created_at):%d/%m/%Y %H:%M} · PK-{m.document_id:06d} · "
        f"kho {m.warehouse.code} · {m.product.sku}: "
        f"{'+' if m.delta > 0 else ''}{number(m.delta)} → tồn sau {number(m.balance_after)}"
        for m in rows
    ]
    head = f"{len(rows)} biến động gần nhất (tối đa {MAX_ROWS})."
    return ToolResult(
        "\n".join([head, *lines]),
        len(rows),
        [{"label": "Thẻ kho", "url": reverse("ledger")}],
    )


def document_search(user, args):
    qs = documents_for(user).select_related("source", "destination")
    if number_ := _doc_number(args):
        qs = qs.filter(pk=number_)
    kind = _str(args, "kind", 10).upper()
    if kind:
        if kind not in KINDS:
            raise ToolError("kind chỉ nhận " + ", ".join(KINDS) + ".")
        qs = qs.filter(kind=kind)
    status = _str(args, "status", 10).upper()
    if status:
        if status not in STATUSES:
            raise ToolError("status chỉ nhận " + ", ".join(STATUSES) + ".")
        qs = qs.filter(status=status)
    start, end = _range(args)
    if start:
        qs = qs.filter(business_date__gte=start)
    if end:
        qs = qs.filter(business_date__lte=end)
    if _str(args, "sku", 50) or _str(args, "query", 100):
        qs = qs.filter(lines__product__in=_products(args)).distinct()
    code = _str(args, "warehouse_code", 50)
    if code:
        picked = _warehouses(user, args)
        qs = qs.filter(Q(source__in=picked) | Q(destination__in=picked))
    total = qs.count()
    rows = list(qs.order_by("-pk")[:MAX_ROWS])
    head = f"{total} phiếu khớp điều kiện trong phạm vi người hỏi được xem."
    if total > MAX_ROWS:
        head += f" Liệt kê {MAX_ROWS} phiếu mới nhất."
    return ToolResult(
        "\n".join([head, *map(_doc_line, rows)]),
        len(rows),
        [_doc_source(d) for d in rows[:5]],
    )


def document_detail(user, args):
    pk = _doc_number(args)
    if not pk:
        raise ToolError("Cần số phiếu.")
    doc = (
        documents_for(user)
        .select_related("source", "destination", "created_by", "posted_by")
        .filter(pk=pk)
        .first()
    )
    if not doc:
        raise ToolError(f"Không có phiếu PK-{pk:06d} trong phạm vi người hỏi được xem.")
    lines = [_doc_line(doc)]
    lines.append(
        f"Người lập: {doc.created_by.get_full_name() or doc.created_by.username}"
    )
    if doc.posted_by:
        lines.append(
            f"Người ghi sổ: {doc.posted_by.get_full_name() or doc.posted_by.username}"
        )
    for label, value in (
        ("Diễn giải", doc.note),
        ("Đối tác / bộ phận", doc.counterparty or doc.department),
        ("Chứng từ nguồn", doc.reference_number),
        ("Lý do yêu cầu sửa / hủy", doc.closure_reason),
    ):
        if value:
            lines.append(f"{label}: {value[:300]}")
    items = list(doc.lines.select_related("product").order_by("pk")[:MAX_ROWS])
    for item in items:
        price = (
            f" · đơn giá {number(item.unit_price)} đ"
            if item.unit_price is not None
            else ""
        )
        lines.append(
            f"- {item.product.sku} · {item.product.name}: {number(item.quantity)} "
            f"{item.product.unit}{price}"
            + (f" · ghi chú: {item.note[:120]}" if item.note else "")
        )
    return ToolResult("\n".join(lines), len(items), [_doc_source(doc)])


def my_pending_approvals(user, args):
    rows = list(
        approval_documents_for(user)
        .select_related("source", "destination")
        .order_by("pk")[:MAX_ROWS]
    )
    head = f"{len(rows)} phiếu đang chờ người hỏi duyệt hoặc xác nhận nhận."
    return ToolResult(
        "\n".join([head, *map(_doc_line, rows)]),
        len(rows),
        [{"label": "Duyệt phiếu", "url": reverse("approvals")}],
    )


def stocktakes(user, args):
    _need(user, "stocktakes_view", "xem kiểm kê")
    rows = list(
        StocktakeSession.objects.filter(warehouse__in=_warehouses(user, args))
        .select_related("warehouse", "document")
        .order_by("-pk")[:MAX_ROWS]
    )
    lines = [
        f"KK-{s.pk:06d} · kho {s.warehouse.code} · ngày {s.business_date:%d/%m/%Y} · "
        f"{s.workflow_status}"
        for s in rows
    ]
    return ToolResult(
        "\n".join([f"{len(rows)} phiên kiểm kê gần nhất.", *lines]),
        len(rows),
        [{"label": "Kiểm kê", "url": reverse("stocktakes")}],
    )


def loans(user, args):
    _need(user, "loans_view", "xem hàng cho mượn")
    visible = documents_for(user).filter(kind="LOAN")
    qs = LoanHolding.objects.filter(
        loan_line__document__in=visible, quantity__gt=0
    ).select_related(
        "loan_line__product",
        "loan_line__document__source",
        "loan_line__document__destination",
    )
    rows = list(qs.order_by("loan_line__document_id")[:MAX_ROWS])
    lines = []
    for h in rows:
        d = h.loan_line.document
        due = f" · hạn trả {d.due_date:%d/%m/%Y}" if d.due_date else ""
        lines.append(
            f"PK-{d.pk:06d} · {d.source.code if d.source else '—'} cho "
            f"{d.destination.code if d.destination else '—'} mượn · "
            f"{h.loan_line.product.sku}: còn phải trả {number(h.quantity)} "
            f"{h.loan_line.product.unit}{due}"
        )
    return ToolResult(
        "\n".join([f"{len(rows)} dòng hàng mượn chưa trả hết.", *lines]),
        len(rows),
        [{"label": "Mượn & trả", "url": reverse("loans")}],
    )


def deviations(user, args):
    from deviations.access import require_member
    from deviations.constants import TERMINAL, CaseStatus
    from deviations.models import Case

    try:
        require_member(user)
    except PermissionDenied:
        raise ToolError(
            "Người hỏi chưa được cấp quyền xem hồ sơ sai lệch; không được tiết lộ."
        ) from None
    qs = Case.objects.order_by("-pk")
    code = _str(args, "code", 30).upper()
    if code:
        found = re.fullmatch(r"SL-(?:(\d{4})-)?0*(\d{1,12})", code)
        if not found:
            raise ToolError("Mã hồ sơ có dạng SL-2026-000123.")
        qs = qs.filter(pk=int(found[2]))
        if found[1]:
            qs = qs.filter(created_at__year=int(found[1]))
    state = _str(args, "state", 10)
    if state == "open":
        qs = qs.exclude(status__in=TERMINAL)
    elif state == "closed":
        qs = qs.filter(status=CaseStatus.CLOSED)
    elif state not in ("", "all"):
        raise ToolError("state chỉ nhận open, closed hoặc all.")
    total = qs.count()
    rows = list(qs[:MAX_ROWS])
    lines = [f"{c.code} · {c.title} · {c.get_status_display()}" for c in rows]
    return ToolResult(
        "\n".join([f"{total} hồ sơ sai lệch khớp điều kiện.", *lines]),
        len(rows),
        [
            {"label": c.code, "url": reverse("deviation_detail", args=[c.pk])}
            for c in rows[:5]
        ],
    )


def warehouses(user, args):
    _need(user, "warehouses_view", "xem danh mục kho")
    rows = list(warehouses_for(user).order_by("code")[:MAX_ROWS])
    return ToolResult(
        "\n".join(
            [f"{len(rows)} kho người hỏi được xem."]
            + [f"{w.code} · {w.name}" for w in rows]
        ),
        len(rows),
        [{"label": "Kho hàng", "url": reverse("warehouse_list")}],
    )


def user_guide(user, args):
    question = _str(args, "question", 300)
    article = find_article(question, None) if question else None
    if article:
        return ToolResult(f"{article.title}\n{article.answer}", 1)
    topics = "; ".join(title for title, _guide, _ in GUIDES.values())
    known = "; ".join(a.title for a in ARTICLES[:40])
    return ToolResult(
        "Không có bài hướng dẫn khớp đúng câu hỏi. Các mục có hướng dẫn: "
        + topics
        + ". Bài hướng dẫn: "
        + known,
        0,
    )


def _spec(name, description, properties=None, required=()):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "required": list(required),
                "additionalProperties": False,
            },
        },
    }


_PRODUCT = {
    "sku": {"type": "string", "description": "Mã hàng chính xác, ví dụ THU-001"},
    "query": {"type": "string", "description": "Một phần tên hoặc mã hàng"},
}
_WAREHOUSE = {
    "warehouse_code": {"type": "string", "description": "Mã kho, ví dụ THU-HN"}
}
_DATES = {
    "date_from": {"type": "string", "description": "YYYY-MM-DD"},
    "date_to": {"type": "string", "description": "YYYY-MM-DD"},
}

TOOLS = {
    "product_search": (
        product_search,
        _spec("product_search", "Tìm hàng hóa trong danh mục.", _PRODUCT),
    ),
    "stock": (
        stock,
        _spec(
            "stock",
            "Tồn kho hiện tại theo mã hàng/kho, kèm giá trị và định mức.",
            {
                **_PRODUCT,
                **_WAREHOUSE,
                "filter": {
                    "type": "string",
                    "enum": ["all", "below_minimum", "zero"],
                    "description": "all = có tồn; below_minimum = dưới định mức; zero = hết hàng",
                },
            },
        ),
    ),
    "stock_ledger": (
        stock_ledger,
        _spec(
            "stock_ledger",
            "Thẻ kho: các lần nhập/xuất đã ghi sổ của mã hàng.",
            {**_PRODUCT, **_WAREHOUSE, **_DATES},
        ),
    ),
    "document_search": (
        document_search,
        _spec(
            "document_search",
            "Tìm phiếu kho (nhập, xuất, chuyển, mượn, trả, kiểm kê, điều chỉnh).",
            {
                "number": {
                    "type": "string",
                    "description": "Số phiếu, ví dụ PK-000008",
                },
                "kind": {"type": "string", "enum": list(KINDS)},
                "status": {"type": "string", "enum": list(STATUSES)},
                **_PRODUCT,
                **_WAREHOUSE,
                **_DATES,
            },
        ),
    ),
    "document_detail": (
        document_detail,
        _spec(
            "document_detail",
            "Chi tiết một phiếu: người lập, trạng thái, các dòng hàng.",
            {"number": {"type": "string", "description": "Số phiếu, ví dụ PK-000008"}},
            ["number"],
        ),
    ),
    "my_pending_approvals": (
        my_pending_approvals,
        _spec(
            "my_pending_approvals",
            "Các phiếu đang chờ chính người hỏi duyệt hoặc nhận.",
        ),
    ),
    "stocktakes": (
        stocktakes,
        _spec("stocktakes", "Các phiên kiểm kê gần nhất.", _WAREHOUSE),
    ),
    "loans": (loans, _spec("loans", "Hàng cho mượn chưa trả hết.")),
    "deviations": (
        deviations,
        _spec(
            "deviations",
            "Hồ sơ xử lý sai lệch.",
            {
                "code": {
                    "type": "string",
                    "description": "Mã hồ sơ, ví dụ SL-2026-000012",
                },
                "state": {"type": "string", "enum": ["open", "closed", "all"]},
            },
        ),
    ),
    "warehouses": (
        warehouses,
        _spec("warehouses", "Danh sách kho người hỏi được xem."),
    ),
    "user_guide": (
        user_guide,
        _spec(
            "user_guide",
            "Hướng dẫn thao tác trong phần mềm DHD KSNB.",
            {"question": {"type": "string"}},
            ["question"],
        ),
    ),
}


def specs():
    return [spec for _fn, spec in TOOLS.values()]


def execute(user, name, raw_arguments):
    """Run one tool for `user`. Always returns a ToolResult; never raises for
    bad model input, so a malformed call cannot break the conversation."""
    if name not in TOOLS:
        return ToolResult("Công cụ không tồn tại.")
    try:
        args = json.loads(raw_arguments or "{}")
    except (TypeError, ValueError):
        return ToolResult("Tham số công cụ không phải JSON hợp lệ.")
    if not isinstance(args, dict) or len(json.dumps(args)) > 1000:
        return ToolResult("Tham số công cụ không hợp lệ.")
    try:
        result = TOOLS[name][0](user, args)
    except ToolError as exc:
        return ToolResult(str(exc))
    result.text = _clip(result.text)
    return result


def today_hint():
    today = timezone.localdate()
    return f"Hôm nay là {today:%d/%m/%Y} ({today.isoformat()}); hôm qua {(today - timedelta(days=1)).isoformat()}."
