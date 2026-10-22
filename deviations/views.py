"""Read screens: queries and presentation only; mutations live in mutations.py."""

from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_safe

from inventory.access import has_function, is_admin
from inventory.services import documents_for

from . import access, selectors, storage
from .constants import SEVERITIES, ActionStatus, CaseStatus
from .forms import AssignmentForm, EvaluationForm, UploadForm
from .models import Attachment, Category, WorkflowPolicy
from .workflow import TRANSITIONS


def base_context(user):
    return {
        "can_create": has_function(user, "deviations_create"),
        "can_manage": has_function(user, "deviations_manage"),
        "is_admin": is_admin(user),
        "policy": WorkflowPolicy.objects.filter(pk=1).first(),
    }


def case_for(user, pk):
    access.require_member(user)
    return get_object_or_404(selectors.cases(), pk=pk)


@login_required
@require_safe
def overview(request):
    access.require_member(request.user)
    return render(
        request,
        "deviations/overview.html",
        {
            **base_context(request.user),
            "metrics": selectors.metrics(),
            "recent": selectors.cases()[:6],
        },
    )


@login_required
@require_safe
def case_list(request):
    access.require_member(request.user)
    page = Paginator(selectors.filtered_cases(request.user, request.GET), 25).get_page(
        request.GET.get("page")
    )
    return render(
        request,
        "deviations/list.html",
        {
            **base_context(request.user),
            "page_obj": page,
            "cases": page,
            "categories": Category.objects.all(),
            "statuses": CaseStatus.choices,
            "severities": SEVERITIES,
            "tab": request.GET.get("tab", "all"),
        },
    )


def transition_options(case, user, policy):
    options = []
    for command, spec in TRANSITIONS.items():
        if case.status not in spec.sources or (
            command not in {"submit", "cancel"} and not (policy and policy.enabled)
        ):
            continue
        allowed = is_admin(user)
        if not allowed:
            if spec.review:
                try:
                    access.review(case, user)
                    allowed = True
                except (PermissionDenied, ValidationError):
                    pass
            elif command == "cancel":
                allowed = (
                    case.created_by_id == user.pk
                    and case.status in {CaseStatus.DRAFT, CaseStatus.NEEDS_INFO}
                    and has_function(user, "deviations_create")
                ) or (
                    case.owner_id == user.pk and has_function(user, "deviations_manage")
                )
            elif command == "submit":
                allowed = case.created_by_id == user.pk and has_function(
                    user, "deviations_create"
                )
            else:
                allowed = has_function(user, spec.permission) and (
                    command in {"accept", "need_info", "decline", "duplicate"}
                    or case.owner_id == user.pk
                )
        if allowed:
            options.append(
                {
                    "command": command,
                    "label": spec.label,
                    "reason": spec.reason,
                    "review": spec.review,
                }
            )
    return options


@login_required
@require_safe
def case_detail(request, pk):
    case = case_for(request.user, pk)
    ctx = base_context(request.user)
    manageable = ctx["can_manage"] and (
        is_admin(request.user) or case.owner_id == request.user.pk
    )
    can_review = False
    if case.policy_snapshot:
        try:
            access.review(case, request.user, confirm=True)
            can_review = bool(ctx["policy"] and ctx["policy"].enabled)
        except (PermissionDenied, ValidationError):
            pass
    actions = list(
        case.actions.select_related("assignee").prefetch_related(
            "extensions__requested_by", "extensions__decided_by"
        )
    )
    for action in actions:
        action.can_edit = bool(
            manageable
            and case.status in {CaseStatus.INVESTIGATING, CaseStatus.PLANNING}
            and action.round == case.round
            and ctx["policy"]
            and ctx["policy"].enabled
        )
        action.can_work = bool(
            has_function(request.user, "deviations_work")
            and (is_admin(request.user) or action.assignee_id == request.user.pk)
            and case.status == CaseStatus.EXECUTING
            and action.round == case.round
            and action.status != ActionStatus.DONE
            and ctx["policy"]
            and ctx["policy"].enabled
        )
        action.can_extend = (
            action.can_work and case.policy_snapshot.get("max_extensions") is not None
        )
    events = Paginator(
        case.events.select_related("actor").order_by("-pk"), 20
    ).get_page(request.GET.get("page"))
    return render(
        request,
        "deviations/detail.html",
        {
            **ctx,
            "case": case,
            "actions": actions,
            "can_edit": has_function(request.user, "deviations_create")
            and (is_admin(request.user) or case.created_by_id == request.user.pk)
            and case.status in {CaseStatus.DRAFT, CaseStatus.NEEDS_INFO},
            "can_assign": ctx["can_manage"]
            and not case.is_terminal
            and case.status != CaseStatus.DRAFT,
            "can_analyze": manageable
            and case.status in {CaseStatus.INVESTIGATING, CaseStatus.PLANNING}
            and bool(ctx["policy"] and ctx["policy"].enabled),
            "can_review": can_review,
            "can_evaluate": can_review and case.status == CaseStatus.VERIFYING,
            "transitions": transition_options(case, request.user, ctx["policy"]),
            "assignment_form": AssignmentForm(
                initial={"revision": case.revision, "owner": case.owner_id}
            ),
            "upload_form": UploadForm(case=case),
            "can_upload": storage.can_upload(case, request.user),
            "evaluation_form": EvaluationForm(initial={"revision": case.revision}),
            "attachments": case.attachments.select_related(
                "uploaded_by", "action", "voided_by", "file"
            ).defer("file__data"),
            "evaluations": case.evaluations.select_related("checked_by").order_by(
                "-pk"
            ),
            "events": events,
            "page_obj": events,
            "source_document_visible": case.source_document_id
            and documents_for(request.user).filter(pk=case.source_document_id).exists(),
            "source_product_visible": has_function(request.user, "products_view"),
        },
    )


@login_required
@require_safe
def reports(request):
    access.require_member(request.user)
    return render(
        request,
        "deviations/reports.html",
        {
            **base_context(request.user),
            "metrics": selectors.metrics(),
            "groups": selectors.category_report(),
        },
    )


@login_required
@require_safe
def print_case(request, pk):
    case = case_for(request.user, pk)
    return render(
        request,
        "deviations/print.html",
        {
            "case": case,
            "actions": case.actions.select_related("assignee"),
            "evaluations": case.evaluations.select_related("checked_by"),
            "events": case.events.select_related("actor"),
            "attachments": case.attachments.select_related("file").defer("file__data"),
        },
    )


@login_required
@require_safe
def evidence_file(request, pk):
    access.require_member(request.user)
    attachment = get_object_or_404(
        Attachment.objects.only("file_id", "filename"), pk=pk
    )
    try:
        file, data = storage.content(attachment.file_id)
    except ValidationError as exc:
        return HttpResponse(
            " ".join(exc.messages), status=503, content_type="text/plain; charset=utf-8"
        )
    response = FileResponse(
        BytesIO(data),
        content_type=file.content_type,
        filename=attachment.filename,
        as_attachment=not file.content_type.startswith("image/"),
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response
