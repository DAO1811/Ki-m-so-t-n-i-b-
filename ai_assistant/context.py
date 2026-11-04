"""Grounded answers first; no model, remote call, or company-data cache in this path."""

import re

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.urls import Resolver404, resolve, reverse
from django.utils import timezone

from inventory.access import has_function
from inventory.services import documents_for, warehouses_for

from .data import (
    catalog_answer,
    deviations_answer,
    document_filters,
    documents_answer,
    product_selector,
    stock_answer,
    stocktakes_answer,
    warehouse_code,
    warehouses_answer,
)
from .guides import GUIDES, topic_for
from .knowledge import draft_answer, explicit_topic, find_article
from .text import any_phrase, plain

TOKEN_SALT = "assistant.read-context.v2"


def require_use(user):
    if (
        not user.is_authenticated
        or not user.is_active
        or not has_function(user, "assistant_use")
    ):
        raise PermissionDenied("Bạn chưa được cấp quyền dùng Trợ lý AI.")


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


def read_continuation(token, user, path, warehouse):
    if not isinstance(token, str) or len(token) > 2000:
        raise ValueError("Ngữ cảnh không hợp lệ.")
    if not token:
        return {}
    try:
        data = signing.loads(token, salt=TOKEN_SALT, max_age=900)
    except signing.BadSignature:
        return {}
    if (
        data.get("user") != user.pk
        or data.get("path") != path
        or data.get("warehouse") != str(warehouse)
    ):
        return {}
    return data.get("query", {})


# Link only to an existing screen the account can open. Permission checks still
# run again at that screen; these links confer no additional access.
HELP_LINKS = {
    "products": ("products", "products_view"),
    "receipts": ("documents", "receipts_view"),
    "issues": ("documents", "issues_view"),
    "transfers": ("documents", "transfers_view"),
    "documents": ("documents", "documents_view"),
    "stock": ("stock", "stock_view"),
    "loans": ("loans", "loans_view"),
    "stocktakes": ("stocktakes", "stocktakes_view"),
    "team": ("team", "team_view"),
    "chat": ("chat_home", "chat_use"),
    "deviations": ("deviations", None),
    "drive": ("drive_settings", "admin"),
    "storage": ("storage_settings", "admin"),
}


def help_sources(user, topic, title, article):
    # Excel entry points differ: a link must not send users to the wrong import.
    specials = {
        "receipt_excel": ("receipt_import", "receipts_create"),
        "catalog_excel": ("product_import", "products_create"),
        "issue_excel": ("issue_import", "issues_create"),
        "product_qr": ("product_new", "products_create"),
    }
    target = specials.get(article.key) if article else None
    target = target or HELP_LINKS.get(topic)
    if not target:
        return []
    route, grant = target
    if grant == "admin":
        allowed = user.is_superuser
    else:
        allowed = grant is None or has_function(user, grant)
    if not allowed:
        return []
    url = reverse(route)
    kind = {"receipts": "IN", "issues": "OUT", "transfers": "TRANSFER"}.get(topic)
    if route == "documents" and kind:
        url += "?kind=" + kind
    return [{"label": title, "url": url}]


def context_for(user, question, path, warehouse="", continuation=""):
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
    page_topic = topic_for(route, kind)
    norm = plain(question)
    explicit = explicit_topic(norm)
    previous = read_continuation(continuation, user, path, warehouse)
    followup = any_phrase(
        norm,
        (
            "no",
            "do",
            "nay",
            "vay",
            "the",
            "tiep theo",
            "buoc tiep",
            "con",
            "tong",
            "them",
            "tiep tuc",
        ),
    )
    inherited = (
        previous
        if followup and (not explicit or explicit == previous.get("topic"))
        else {}
    )
    topic = explicit or inherited.get("topic") or page_topic
    title, guide, _ = GUIDES.get(topic, GUIDES["general"])
    response = {
        "page": GUIDES.get(page_topic, GUIDES["general"])[0],
        "topic": topic,
        "guide": guide,
        "at": timezone.localtime().isoformat(),
        "sources": [],
        "facts": [],
        "answer": guide,
        "scope": "help",
        "answer_kind": "knowledge",
        "can_refine": False,
        "notice": "Hướng dẫn đối chiếu chức năng hiện có; không thực hiện giao dịch thay người dùng.",
    }
    allowed = warehouses_for(user)
    scoped = bool(warehouse)
    if warehouse:
        if (
            not str(warehouse).isdigit()
            or len(str(warehouse)) > 18
            or not allowed.filter(pk=warehouse).exists()
        ):
            raise PermissionDenied("Kho nằm ngoài phạm vi được phép.")
        allowed = allowed.filter(pk=warehouse)

    selector = product_selector(question)
    filters = document_filters(question)
    article = find_article(question, topic)
    guidance = any_phrase(
        norm,
        (
            "huong dan",
            "lam sao",
            "the nao",
            "cach",
            "can dien",
            "quy trinh",
            "o dau",
            "cho nao",
            "vi sao",
            "tai sao",
            "soan",
            "viet",
            "goi y",
            "nhac",
            "dung de lam gi",
            "co duoc",
            "duoc khong",
            "dung de",
            "duyet phieu",
            "tao phieu",
            "tao san pham",
            "tao nhom",
            "them hang",
            "import",
            "excel",
            "sua phieu",
            "xoa phieu",
            "xoa kiem ke",
        ),
    )
    data_question = any_phrase(
        norm,
        (
            "bao nhieu",
            "tra cuu",
            "xem",
            "danh sach",
            "cac phieu",
            "nhung phieu",
            "cac ho so",
            "hien tai",
            "hom nay",
            "trang thai",
            "cho duyet",
            "chua duyet",
            "tong",
            "con",
            "ton",
            "ton kho",
            "sap het",
            "het hang",
            "kho nao",
            "cac kho",
            "phieu nay",
            "phieu do",
        ),
    ) or bool(selector or filters.get("pk") or re.search(r"\bsl-\d", norm))
    lookup_domain = any_phrase(
        norm,
        (
            "ton",
            "phieu",
            "hang",
            "ma",
            "danh muc",
            "ho so",
            "sai lech",
            "kho",
            "kiem ke",
            "gia tri",
            "nhap",
            "xuat",
            "muon",
            "tra hang",
        ),
    ) or bool(
        selector
        or doc
        or (previous and followup)
        or route == "product_detail"
        or re.search(r"\bsl-\d", norm)
    )
    data_question = data_question and lookup_domain
    dependent_without_context = (
        any_phrase(norm, ("vay", "the", "no", "phieu do", "ma do"))
        and not previous
        and explicit in {None, "stock"}
        and not selector
        and not filters.get("pk")
        and not doc
        and route != "product_detail"
        and not guidance
        and not article
    )
    scope = "help"
    if filters.get("pk") or (
        doc
        and any_phrase(norm, ("phieu nay", "phieu do", "phieu", "buoc tiep", "duyet"))
        and not guidance
    ):
        scope = "documents"
    elif data_question and not guidance:
        if re.search(r"\bsl-\d", norm) or topic == "deviations":
            scope = "deviations"
        elif topic == "stocktakes":
            scope = "stocktakes"
        elif (
            any_phrase(norm, ("phieu", "cho duyet", "chua duyet"))
            or filters.get("kind")
            or inherited.get("scope") == "documents"
        ):
            scope = "documents"
        elif topic == "stock" or selector or inherited.get("scope") == "stock":
            scope = "stock"
            if topic == "products" and any_phrase(
                norm, ("qr", "ten", "don vi", "anh", "thong tin")
            ):
                scope = "catalog"
        elif explicit == "products":
            scope = "catalog"
        elif any_phrase(norm, ("cac kho", "kho nao", "danh sach kho")):
            scope = "warehouses"
    if inherited and scope == "help" and (data_question or followup) and not guidance:
        scope = inherited.get("scope", "help")
    if inherited.get("selector") and not selector:
        if not filters.get("pk"):
            selector = inherited["selector"]
    if inherited.get("filters") and scope == "documents" and not filters.get("pk"):
        old_filters = inherited["filters"].copy()
        if "business_date" in filters or "business_date__range" in filters:
            old_filters.pop("business_date", None)
            old_filters.pop("business_date__range", None)
        filters = {**old_filters, **filters}
    if scope == "documents" and any_phrase(norm, ("cua toi", "toi lap", "toi tao")):
        filters["created_by_id"] = user.pk
    if (
        scope in {"stock", "catalog"}
        and route == "product_detail"
        and isinstance(pk, int)
        and not selector
    ):
        selector = {"product_id": pk}
    if scope == "documents" and doc and not filters.get("pk"):
        filters["pk"] = doc.pk
    code = None
    if scope != "help":
        if code := warehouse_code(question):
            allowed = allowed.filter(code__iexact=code)
            scoped = True
            if not allowed.exists():
                raise PermissionDenied(
                    "Không tìm thấy kho yêu cầu trong phạm vi bạn được xem."
                )
        elif inherited.get("warehouse_code"):
            # Always reapply current permissions; a signed token is never a grant.
            allowed = allowed.filter(code__iexact=inherited["warehouse_code"])
            scoped = True
    query = {"topic": topic, "scope": scope}
    if selector:
        query["selector"] = selector
    if filters:
        query["filters"] = filters
    if code or inherited.get("warehouse_code"):
        query["warehouse_code"] = code or inherited["warehouse_code"]
    if dependent_without_context:
        scope = "help"
        response.update(
            answer="Bạn đang hỏi về mã hàng hoặc phiếu nào? Ngữ cảnh trước chưa có hoặc đã hết hạn; vui lòng ghi lại mã/số phiếu để tôi tra cứu đúng dữ liệu mới.",
            answer_kind="clarification",
        )
    elif scope == "stock" and (
        any_phrase(norm, ("hom qua", "thang truoc", "truoc day"))
        or re.search(r"\d{1,2}/\d{1,2}/\d{4}", norm)
    ):
        scope = "help"
        response.update(
            answer="Tra cứu tồn trực tiếp hiện trả số tồn hiện tại, chưa tính số dư tại ngày quá khứ trong khung này. Hãy mở Thẻ kho và lọc đúng hàng, kho, khoảng ngày để đối chiếu tồn sau từng giao dịch; tôi không thay số tồn lịch sử bằng số hiện tại.",
            answer_kind="clarification",
        )
    elif scope == "stock":
        response.update(stock_answer(user, question, allowed, selector))
    elif scope == "catalog":
        response.update(catalog_answer(user, question, selector))
    elif scope == "documents":
        response.update(
            documents_answer(user, question, allowed, filters, selector, scoped)
        )
    elif scope == "deviations":
        case_pk = (
            pk
            if route.startswith("deviation_") and isinstance(pk, int)
            else inherited.get("case_pk")
        )
        response.update(deviations_answer(user, question, case_pk))
        found = re.search(r"\bSL-(\d{4})-(\d{1,12})\b", question, re.I)
        if found and response["facts"]:
            query["case_pk"] = int(found[2])
    elif scope == "stocktakes":
        response.update(stocktakes_answer(user, allowed))
    elif scope == "warehouses":
        response.update(warehouses_answer(user, allowed))
    else:
        draft = draft_answer(norm)
        if draft:
            response.update(answer=draft, answer_kind="draft", can_refine=True)
        elif article:
            title = article.title
            response.update(answer=article.answer, can_refine=True)
            topic = article.topic
            query["topic"] = topic
        elif (
            guidance
            and (
                explicit
                or norm in {"huong dan", "cach dung"}
                or any_phrase(norm, ("muc nay", "trang nay", "phieu nay"))
            )
        ) or (inherited and inherited.get("scope") == "help"):
            response.update(answer=guide, can_refine=topic != "general")
        elif any_phrase(norm, ("xin chao", "chao", "hello", "giup gi", "lam duoc gi")):
            response["answer"] = (
                "Tôi có thể hướng dẫn thao tác trong phần mềm, tra cứu tồn theo mã/kho, kiểm tra trạng thái phiếu và hồ sơ sai lệch trong quyền của bạn. Bạn đang cần làm việc gì? Ví dụ: ‘Trả hàng đã mượn thế nào?’ hoặc ‘Mã AI001 còn bao nhiêu?’"
            )
        else:
            response.update(
                answer="Tôi chưa xác định đủ yêu cầu để trả lời chắc chắn. Bạn muốn hướng dẫn thao tác hay tra cứu dữ liệu? Hãy ghi tên chức năng, mã hàng, số phiếu hoặc tên hàng trong dấu ngoặc kép. Tôi không tự suy đoán hoặc đưa số liệu không liên quan.",
                answer_kind="clarification",
            )
        response["sources"] = help_sources(user, topic, title, article)
    response["scope"] = scope
    response["topic"] = topic
    if scope != "help":
        topic = {
            "stock": "stock",
            "catalog": "products",
            "documents": "documents",
            "deviations": "deviations",
            "stocktakes": "stocktakes",
        }.get(scope, topic)
        query["topic"] = topic
        response["topic"] = topic
        response["answer_kind"] = "live"
        response["can_refine"] = False
        response.setdefault(
            "notice", "Dữ liệu mới tại thời điểm hỏi, theo quyền và kho được cấp."
        )
        if response["notice"].startswith("Hướng dẫn"):
            response["notice"] = (
                "Dữ liệu mới tại thời điểm hỏi, chỉ trong kho và chức năng tài khoản được cấp; không gồm kho ngoài quyền."
            )
    response["continuation"] = signing.dumps(
        {"user": user.pk, "path": path, "warehouse": str(warehouse), "query": query},
        salt=TOKEN_SALT,
        compress=True,
    )
    return response
