"""Allowlisted, bounded live queries. These selectors never mutate company data."""

import re
from datetime import date, timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.core.exceptions import PermissionDenied
from django.db.models import Count, F, Q, Sum
from django.urls import reverse
from django.utils import timezone

from inventory.access import has_function
from inventory.models import Balance, Product, StocktakeSession
from inventory.services import approval_block_reason, documents_for

from .text import any_phrase, plain

MAX_ROWS = 8


def number(value):
    text = format(value or Decimal(0), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def product_selector(question):
    if code := warehouse_code(question):
        question = re.sub(
            r"\bkho\s+(?:mã\s+|ma\s+)?" + re.escape(code) + r"(?!\w)",
            "",
            question,
            flags=re.I,
        )
    codes = re.findall(
        r"(?<!\w)[A-Za-z][A-Za-z0-9_.-]*\d[A-Za-z0-9_.-]*(?!\w)", question
    )
    # A deviation code is not an SKU. Dates/numeric IDs are never guessed as SKUs.
    codes = [c for c in codes if not re.fullmatch(r"SL-\d{4}-\d+", c, re.I)]
    if codes:
        return {"codes": list(dict.fromkeys(codes))[:5]}
    match = re.search(
        r"(?:mã hàng|mã sản phẩm|ma hang|ma san pham|sku|mã)\s*[:#]?\s*([\w.-]{1,100})",
        question,
        re.I,
    )
    if match and plain(match[1]) not in {
        "nay",
        "nao",
        "gi",
        "cua",
        "dang",
        "da",
        "con",
        "hien",
    }:
        return {"codes": [match[1]]}
    match = re.search(r'["“]([^"”]{2,100})["”]', question)
    if match:
        return {"term": match[1]}
    # Common unquoted natural-language lookup: "máy ảnh còn bao nhiêu".
    match = re.match(
        r"\s*(.+?)\s+(?:còn bao nhiêu|con bao nhieu|tồn bao nhiêu|ton bao nhieu)",
        question,
        re.I,
    )
    if (
        match
        and plain(match[1]).strip()
        not in {"vay", "the", "con", "no", "hang nay", "ma nay", "san pham nay"}
        and not any_phrase(
            plain(match[1]), ("kho", "phieu", "tong", "tat ca", "cong ty")
        )
    ):
        return {"term": match[1].strip()[:100]}
    return {}


def product_filter(selector):
    if selector.get("product_id"):
        return Q(pk=selector["product_id"])
    if selector.get("codes"):
        query = Q(pk__in=[])
        for code in selector["codes"]:
            query |= Q(sku__iexact=code)
        return query
    if selector.get("term"):
        return Q(name__icontains=selector["term"]) | Q(sku__iexact=selector["term"])
    return Q()


def warehouse_code(question):
    match = re.search(
        r"\bkho\s+(?:mã\s+|ma\s+)?([A-Za-z0-9_-]{1,50})(?!\w)", question, re.I
    )
    if match and plain(question[: match.start()]).rstrip().endswith("ton"):
        return None
    if match and plain(match[1]) not in {
        "hien",
        "nay",
        "nao",
        "gi",
        "duoc",
        "dang",
        "con",
        "co",
        "khac",
        "nhap",
        "xuat",
        "theo",
        "cua",
        "bao",
        "trong",
        "tat",
        "tong",
        "da",
        "toi",
    }:
        return match[1]
    return None


def stock_answer(user, question, warehouses, selector):
    if not has_function(user, "stock_view"):
        if not has_function(user, "products_view"):
            return {
                "answer": "Bạn chưa được cấp quyền xem danh mục hoặc tồn kho. Nhờ Admin phân quyền phù hợp trước khi tra cứu.",
                "facts": [],
                "sources": [],
            }
        rows = list(
            Product.objects.filter(product_filter(selector)).order_by("sku")[:MAX_ROWS]
        )
        facts = [f"{p.sku} · {p.name} · Đơn vị {p.unit}" for p in rows]
        return {
            "answer": "Bạn có quyền xem danh mục, chưa có quyền xem số tồn.\n"
            + ("\n".join(facts) or "Không tìm thấy mã hàng phù hợp."),
            "facts": facts,
            "sources": [
                {"label": p.sku, "url": reverse("product_detail", args=[p.pk])}
                for p in rows
            ],
        }
    norm = plain(question)
    qs = Balance.objects.filter(
        warehouse__in=warehouses,
        product__in=Product.objects.filter(product_filter(selector)),
    )
    if any_phrase(norm, ("sap het", "duoi dinh muc", "ton thap", "ton toi thieu")):
        qs = qs.filter(quantity__lt=F("product__minimum"))
    elif any_phrase(norm, ("het hang", "ton bang 0")):
        qs = qs.filter(quantity=0)
    if any_phrase(norm, ("tong", "gia tri", "bao nhieu ma")):
        totals = qs.aggregate(
            rows=Count("pk"),
            products=Count("product", distinct=True),
            value=Sum("value"),
        )
        units = list(
            qs.values("product__unit")
            .annotate(total=Sum("quantity"))
            .order_by("product__unit")[:6]
        )
        facts = [
            f"{totals['products']} mã hàng · {totals['rows']} dòng tồn · Tổng giá trị tồn sở hữu {number(totals['value'])} đ."
        ]
        facts.extend(
            f"Tổng theo đơn vị {row['product__unit']}: {number(row['total'])}."
            for row in units[:5]
        )
        if len(units) > 5:
            facts.append(
                "Có thêm đơn vị tính; mở Tồn kho để xem chi tiết. Không cộng khác đơn vị thành một số lượng."
            )
        return {
            "facts": facts,
            "answer": "\n".join(facts),
            "sources": [],
            "notice": "Tổng tính trên các dòng tồn khớp bộ lọc, trong kho được phép xem; không gồm hàng đang chuyển hoặc mượn tạm. Mã chưa có dòng tồn không nằm trong số mã trên.",
        }
    rows = list(
        qs.select_related("product", "warehouse").order_by(
            "warehouse__code", "product__sku"
        )[: MAX_ROWS + 1]
    )
    facts = [
        f"{r.product.sku} · {r.product.name}: kho {r.warehouse.code}, tồn sở hữu {number(r.quantity)} {r.product.unit}."
        for r in rows[:MAX_ROWS]
    ]
    answer = (
        "\n".join(facts)
        or "Không có dòng tồn phù hợp trong phạm vi kho được cấp quyền. Không suy ra rằng toàn công ty không có hàng."
    )
    if len(rows) > MAX_ROWS:
        answer += "\nĐang hiển thị 8 dòng đầu, chưa phải tổng hợp toàn bộ. Ghi rõ mã hàng hoặc hỏi tổng trong phạm vi đang xem."
    return {
        "facts": facts,
        "answer": answer,
        "sources": [
            {
                "label": f"{r.warehouse.code} · {r.product.sku}",
                "url": reverse("stock")
                + "?"
                + urlencode({"warehouse": r.warehouse_id, "q": r.product.sku}),
            }
            for r in rows[:MAX_ROWS]
        ],
    }


def catalog_answer(user, question, selector):
    if not has_function(user, "products_view"):
        return {
            "answer": "Bạn chưa được cấp quyền xem danh mục hàng hóa.",
            "facts": [],
            "sources": [],
        }
    qs = Product.objects.filter(product_filter(selector)).order_by("sku")
    if any_phrase(plain(question), ("bao nhieu", "tong", "dem ma")):
        facts = [
            f"Có {qs.count()} mã hàng khớp bộ lọc trong danh mục; đây là số mã, không phải số lượng tồn kho."
        ]
        return {
            "answer": "\n".join(facts),
            "facts": facts,
            "sources": [{"label": "Danh mục hàng hóa", "url": reverse("products")}],
        }
    rows = list(qs[: MAX_ROWS + 1])
    facts = [
        f"{p.sku} · {p.name} · Đơn vị {p.unit} · Nhóm {p.category or 'chưa khai báo'} · QR {p.qr_value}"
        for p in rows[:MAX_ROWS]
    ]
    return {
        "answer": "\n".join(facts) or "Không tìm thấy mã hàng phù hợp trong danh mục.",
        "facts": facts,
        "sources": [
            {
                "label": f"{p.sku} · Mở thông tin và ảnh",
                "url": reverse("product_detail", args=[p.pk]),
            }
            for p in rows[:MAX_ROWS]
        ],
        "notice": "Tối đa 8 mã đầu khớp bộ lọc; ảnh xem tại hồ sơ hàng hóa. Không tự đọc hoặc gửi tệp ảnh cho mô hình.",
    }


def document_filters(question):
    norm = plain(question)
    result = {}
    if found := re.search(
        r"(?:\bphieu\s*(?:(?:nhap|xuat|chuyen|muon|tra|dieu chinh)\s*)?(?:so\s*)?#?\s*|#)(\d{1,12})(?!\d)",
        norm,
    ):
        result["pk"] = int(found[1])
    kinds = (
        ("phieu tra", "RETURN"),
        ("tra hang", "RETURN"),
        ("muon", "LOAN"),
        ("chuyen", "TRANSFER"),
        ("nhap", "IN"),
        ("xuat", "OUT"),
        ("dieu chinh", "ADJUST"),
    )
    for word, kind in kinds:
        if any_phrase(norm, (word,)):
            result["kind"] = kind
            break
    for words, status in (
        (("cho duyet", "chua duyet", "phieu nhap chua", "ban nhap"), "DRAFT"),
        (("da ghi so", "da duyet", "hoan tat"), "POSTED"),
        (("dang chuyen", "cho nhan"), "TRANSIT"),
        (("yeu cau sua", "bi tra lai"), "REJECTED"),
        (("da huy",), "CANCELLED"),
    ):
        if any_phrase(norm, words):
            result["status"] = status
            break
    dates = re.findall(r"(?<!\d)(\d{1,2})/(\d{1,2})/(\d{4})(?!\d)", norm)
    if dates:
        values = [date(int(y), int(m), int(d)) for d, m, y in dates]
        if len(values) > 2 or (
            len(values) == 2 and not 0 <= (values[1] - values[0]).days <= 366
        ):
            raise ValueError("Khoảng ngày không hợp lệ.")
        result["business_date__range"] = [
            v.isoformat() for v in (values if len(values) == 2 else values * 2)
        ]
    elif any_phrase(norm, ("hom nay",)):
        result["business_date"] = timezone.localdate().isoformat()
    elif any_phrase(norm, ("hom qua",)):
        result["business_date"] = (timezone.localdate() - timedelta(days=1)).isoformat()
    elif any_phrase(norm, ("thang nay",)):
        today = timezone.localdate()
        result["business_date__range"] = [
            today.replace(day=1).isoformat(),
            today.isoformat(),
        ]
    return result


def documents_answer(user, question, warehouses, filters, selector, scoped):
    qs = (
        documents_for(user)
        .select_related("source", "destination", "created_by")
        .order_by("-pk")
    )
    if scoped:
        qs = qs.filter(Q(source__in=warehouses) | Q(destination__in=warehouses))
    qs = qs.filter(**filters)
    if selector:
        qs = qs.filter(
            lines__product__in=Product.objects.filter(product_filter(selector))
        ).distinct()
    norm = plain(question)
    if any_phrase(norm, ("bao nhieu phieu", "tong", "dem phieu")):
        count = qs.count()
        facts = [f"Có {count} phiếu khớp bộ lọc trong phạm vi bạn được xem."]
        if scoped:
            facts.append("Đã giới hạn theo kho đang chọn.")
        return {"answer": "\n".join(facts), "facts": facts, "sources": []}
    rows = list(qs[: MAX_ROWS + 1])
    facts = [
        f"Phiếu #{d.pk} · {d.get_kind_display()} · {d.get_status_display()} · ngày {d.business_date:%d/%m/%Y}"
        for d in rows[:MAX_ROWS]
    ]
    if (
        filters.get("pk")
        and len(rows) == 1
        and any_phrase(norm, ("duyet", "xu ly", "buoc tiep", "tiep theo"))
    ):
        d = rows[0]
        if d.status in {"DRAFT", "TRANSIT"}:
            reason = approval_block_reason(d, user)
            facts.append(
                "Tài khoản hiện tại: "
                + (
                    reason
                    or "Đủ điều kiện về cấp, quyền và phân công cho bước duyệt/nhận. Vẫn phải kiểm tra nội dung, ngày, tồn và điều kiện phiếu trước khi xác nhận."
                )
            )
        else:
            facts.append(
                "Phiếu không ở trạng thái chờ duyệt/chờ nhận; không thể duyệt lại bước này."
            )
    answer = (
        "\n".join(facts)
        or "Không tìm thấy phiếu phù hợp được phép xem. Quyền hỏi trợ lý không mở thêm quyền xem phiếu."
    )
    if len(rows) > MAX_ROWS:
        answer += "\nCó thêm phiếu phù hợp; đang hiển thị 8 phiếu gần nhất. Hỏi tổng số phiếu để đếm đầy đủ trong bộ lọc."
    return {
        "answer": answer,
        "facts": facts,
        "sources": [
            {"label": f"Phiếu #{d.pk}", "url": reverse("document_detail", args=[d.pk])}
            for d in rows[:MAX_ROWS]
        ],
        "notice": "Tối đa 8 phiếu gần nhất khớp bộ lọc. Phiếu nháp chưa thay đổi tồn; điều kiện duyệt vẫn được kiểm tra tại phiếu.",
    }


def deviations_answer(user, question, pk=None):
    from deviations.access import require_member
    from deviations.constants import TERMINAL, CaseStatus
    from deviations.models import Case

    require_member(user)
    norm = plain(question)
    qs = Case.objects.order_by("-pk")
    if pk:
        qs = qs.filter(pk=pk)
    elif found := re.search(r"\bSL-(\d{4})-(\d{1,12})\b", question, re.I):
        qs = qs.filter(pk=int(found[2]), created_at__year=int(found[1]))
    elif found := re.search(r"\bSL-?(\d{1,12})\b", question, re.I):
        qs = qs.filter(pk=int(found[1]))
    if any_phrase(norm, ("chua ket thuc", "dang xu ly")):
        qs = qs.exclude(status__in=TERMINAL)
    elif any_phrase(norm, ("da ket thuc",)):
        qs = qs.filter(status=CaseStatus.CLOSED)
    if any_phrase(norm, ("bao nhieu", "tong", "dem ho so")):
        facts = [f"Có {qs.count()} hồ sơ sai lệch khớp bộ lọc."]
        return {"answer": "\n".join(facts), "facts": facts, "sources": []}
    rows = list(qs[:7])
    facts = [f"{c.code} · {c.title} · {c.get_status_display()}" for c in rows[:6]]
    return {
        "answer": "\n".join(facts) or "Chưa có hồ sơ phù hợp.",
        "facts": facts,
        "sources": [
            {"label": c.code, "url": reverse("deviation_detail", args=[c.pk])}
            for c in rows[:6]
        ],
        "notice": "Nhân viên được xem hồ sơ sai lệch theo quy tắc công ty hiện có; quyền sửa/xác nhận cấp riêng. Tối đa 6 hồ sơ; không đọc nội dung điều tra hoặc tệp đính kèm.",
    }


def stocktakes_answer(user, warehouses):
    if not has_function(user, "stocktakes_view"):
        return {
            "answer": "Bạn chưa được cấp quyền xem phiên kiểm kê.",
            "facts": [],
            "sources": [],
        }
    qs = (
        StocktakeSession.objects.filter(warehouse__in=warehouses)
        .select_related("warehouse", "document")
        .order_by("-pk")
    )
    rows = list(qs[:MAX_ROWS])
    from inventory.stocktakes import active_sessions

    locked_ids = set(
        active_sessions()
        .filter(locks_inventory=True, pk__in=[s.pk for s in rows])
        .values_list("pk", flat=True)
    )
    facts = [
        f"KK-{s.pk:06d} · kho {s.warehouse.code} · {s.workflow_status} · {'đang khóa kiểm đếm' if s.pk in locked_ids else 'không khóa kiểm đếm'}."
        for s in rows
    ]
    return {
        "answer": "\n".join(facts)
        or "Chưa có phiên kiểm kê trong các kho bạn được xem.",
        "facts": facts,
        "sources": [
            {"label": f"KK-{s.pk:06d}", "url": reverse("stocktake_detail", args=[s.pk])}
            for s in rows
        ],
        "notice": "Tối đa 8 phiên gần nhất trong kho được cấp; không tự hủy, mở kho hay duyệt điều chỉnh.",
    }


def warehouses_answer(user, warehouses):
    if not has_function(user, "warehouses_view"):
        raise PermissionDenied("Bạn chưa được cấp quyền xem danh mục kho.")
    rows = list(warehouses.order_by("code")[: MAX_ROWS + 1])
    facts = [f"{w.code} · {w.name}" for w in rows[:MAX_ROWS]]
    return {
        "answer": "\n".join(facts) or "Chưa có kho trong phạm vi được cấp.",
        "facts": facts,
        "sources": [
            {"label": "Danh sách kho được cấp", "url": reverse("warehouse_list")}
        ],
        "notice": "Tối đa 8 kho; chỉ các kho tài khoản được cấp quyền.",
    }
