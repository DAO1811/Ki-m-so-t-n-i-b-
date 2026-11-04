"""Read-only context retrieval. AI never chooses permissions or executes SQL."""

import re
import unicodedata

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone

from inventory.access import has_function
from inventory.models import Balance, Product
from inventory.services import documents_for, warehouses_for

from .guides import GUIDES, topic_for


def plain(value):
    return "".join(
        c
        for c in unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
        if not unicodedata.combining(c)
    )


def require_use(user):
    if (
        not user.is_authenticated
        or not user.is_active
        or not has_function(user, "assistant_use")
    ):
        raise PermissionDenied("Bạn chưa được cấp quyền dùng Trợ lý AI.")


def quantity_label(quantity):
    text = format(quantity, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def page_info(path):
    if (
        not isinstance(path, str)
        or not path.startswith("/")
        or path.startswith("//")
        or len(path) > 300
        or "?" in path
        or "#" in path
    ):
        raise ValueError("Trang không hợp lệ.")
    try:
        match = resolve(path)
        return match.url_name or "", match.kwargs
    except Resolver404:
        return "", {}


def product_filter(q):
    tokens = re.findall(r"[\w.-]{1,60}", q)[:40]
    exact = Q(pk__in=[])
    typed_codes = [
        t
        for t in tokens
        if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]*\d[A-Za-z0-9_.-]*", t)
    ]
    if typed_codes:
        for token in typed_codes:
            exact |= Q(sku__iexact=token)
        return exact
    for token in tokens:
        exact |= Q(sku__iexact=token)
    if tokens and Product.objects.filter(exact).exists():
        return exact
    explicit = re.search(r"(?:mã hàng|mã|sku)\s*[:#]?\s*([\w.-]{1,50})", q, re.I)
    if explicit and plain(explicit[1]) not in {"nay", "nao", "gi", "cua", "dang"}:
        return Q(sku__iexact=explicit[1])
    quoted = re.search(r'["“]([^"”]{2,60})["”]', q)
    if quoted:
        return Q(sku__icontains=quoted[1]) | Q(name__icontains=quoted[1])
    return Q()


def context_for(user, question, path, warehouse=""):
    require_use(user)
    route, kwargs = page_info(path)
    kind = str(kwargs.get("kind", "")).upper()
    pk = kwargs.get("pk")
    doc = None
    if route.startswith("document_") and isinstance(pk, int):
        doc = documents_for(user).filter(pk=pk).first()
        if not doc:
            raise PermissionDenied("Không được xem thông tin phiếu này.")
        kind = doc.kind
    topic = topic_for(route, kind)
    norm = plain(question)
    title, guide, _ = GUIDES[topic]
    response = {
        "page": title,
        "guide": guide,
        "at": timezone.localtime().isoformat(),
        "sources": [],
        "facts": [],
        "answer": guide,
        "notice": "Dữ liệu giới hạn theo quyền và phạm vi kho; đây không phải toàn bộ dữ liệu công ty.",
    }
    allowed_warehouses = warehouses_for(user)
    if warehouse:
        if (
            not str(warehouse).isdigit()
            or len(str(warehouse)) > 18
            or not allowed_warehouses.filter(pk=warehouse).exists()
        ):
            raise PermissionDenied("Kho nằm ngoài phạm vi được phép.")
        allowed_warehouses = allowed_warehouses.filter(pk=warehouse)

    # Questions about how to perform an action use help; do not fetch unrelated records.
    guidance = any(
        t in norm
        for t in (
            "huong dan",
            "lam sao",
            "cach ",
            "can dien",
            "quy trinh",
            "soan ",
            "viet ",
            "goi y",
            "nhac ",
        )
    )
    scope = "help"
    if not guidance:
        if (
            any(t in norm for t in ("sai lech", "ho so", "khac phuc"))
            or topic == "deviations"
            or re.search(r"\bsl-\d{4}-\d+\b", norm)
        ):
            scope = "deviations"
        elif any(t in norm for t in ("phieu", "cho duyet")) or doc:
            scope = "documents"
        elif any(
            t in norm for t in ("ton", "con bao nhieu", "ma hang", "hang hoa")
        ) or topic in {"stock", "products"}:
            scope = "stock"
    if scope == "stock":
        if has_function(user, "stock_view"):
            qs = (
                Balance.objects.filter(warehouse__in=allowed_warehouses)
                .select_related("product", "warehouse")
                .order_by("warehouse__code", "product__sku")
            )
            if route == "product_detail" and isinstance(pk, int):
                qs = qs.filter(product_id=pk)
            else:
                qs = qs.filter(
                    product__in=Product.objects.filter(product_filter(question))
                )
            rows = list(qs[:9])
            for row in rows[:8]:
                response["facts"].append(
                    f"{row.product.sku} · {row.product.name}: kho {row.warehouse.code}, tồn sở hữu {quantity_label(row.quantity)} {row.product.unit}."
                )
                response["sources"].append(
                    {
                        "label": f"{row.warehouse.code} · {row.product.sku}",
                        "url": reverse("stock") + f"?warehouse={row.warehouse_id}",
                    }
                )
            response["answer"] = (
                "\n".join(response["facts"])
                or "Không có dòng tồn phù hợp trong phạm vi kho được cấp quyền. Không suy ra rằng toàn công ty không có hàng."
            )
            if len(rows) > 8:
                response["answer"] += (
                    "\nĐang hiển thị 8 dòng đầu, chưa phải tổng hợp toàn bộ. Ghi rõ mã hàng để thu hẹp."
                )
        elif has_function(user, "products_view"):
            qs = Product.objects.filter(product_filter(question)).order_by("sku")
            if route == "product_detail" and isinstance(pk, int):
                qs = qs.filter(pk=pk)
            for p in qs[:8]:
                response["facts"].append(f"{p.sku} · {p.name} · Đơn vị {p.unit}")
                response["sources"].append(
                    {"label": p.sku, "url": reverse("product_detail", args=[p.pk])}
                )
            response["answer"] = (
                "Bạn có quyền xem danh mục, chưa có quyền xem số tồn.\n"
                + "\n".join(response["facts"])
            )
        else:
            response["answer"] = (
                "Bạn chưa được cấp quyền xem danh mục hoặc tồn kho. Nhờ admin phân quyền phù hợp trước khi tra cứu."
            )
    elif scope == "documents":
        qs = documents_for(user).select_related("source", "destination").order_by("-pk")
        if warehouse:
            qs = qs.filter(
                Q(source__in=allowed_warehouses) | Q(destination__in=allowed_warehouses)
            )
        if doc:
            qs = qs.filter(pk=doc.pk)
        else:
            numbers = re.findall(r"(?:phieu\s*(?:so\s*)?|#)(\d{1,12})", norm)
            if numbers:
                qs = qs.filter(pk__in=[int(n) for n in numbers])
            kinds = {
                "nhap": "IN",
                "xuat": "OUT",
                "chuyen": "TRANSFER",
                "tra": "RETURN",
                "muon": "LOAN",
            }
            selected = next(
                (v for k, v in kinds.items() if re.search(r"\b" + k + r"\b", norm)),
                None,
            )
            if selected:
                qs = qs.filter(kind=selected)
            if "cho duyet" in norm or "nhap" == norm:
                qs = qs.filter(status="DRAFT")
        for d in qs[:8]:
            response["facts"].append(
                f"Phiếu #{d.pk} · {d.get_kind_display()} · {d.get_status_display()} · ngày {d.business_date:%d/%m/%Y}"
            )
            response["sources"].append(
                {
                    "label": f"Phiếu #{d.pk}",
                    "url": reverse("document_detail", args=[d.pk]),
                }
            )
        response["answer"] = (
            "\n".join(response["facts"])
            or "Không tìm thấy phiếu phù hợp được phép xem. Quyền hỏi AI không mở thêm quyền xem phiếu."
        )
        response["notice"] = (
            "Tối đa 8 phiếu gần nhất phù hợp; phiếu nháp chưa làm thay đổi tồn."
        )
    elif scope == "deviations":
        from deviations.access import require_member
        from deviations.models import Case

        require_member(user)
        qs = Case.objects.order_by("-pk")
        wanted_year = None
        if route.startswith("deviation_") and isinstance(pk, int):
            qs = qs.filter(pk=pk)
        elif found := re.search(r"\bSL-(\d{4})-(\d{1,12})\b", question, re.I):
            wanted_year = int(found[1])
            qs = qs.filter(pk=int(found[2]))
        elif found := re.search(r"\bSL-?(\d{1,12})\b", question, re.I):
            qs = qs.filter(pk=int(found[1]))
        for case in qs[:6]:
            if wanted_year is not None and case.created_at.year != wanted_year:
                continue
            response["facts"].append(
                f"{case.code} · {case.title} · {case.get_status_display()}"
            )
            response["sources"].append(
                {"label": case.code, "url": reverse("deviation_detail", args=[case.pk])}
            )
        response["answer"] = "\n".join(response["facts"]) or "Chưa có hồ sơ phù hợp."
        response["notice"] = (
            "Theo quy tắc hiện có, nhân viên được xem hồ sơ sai lệch; quyền sửa và xác nhận vẫn được cấp riêng. Tối đa 6 hồ sơ."
        )
    response["scope"] = scope
    return response
