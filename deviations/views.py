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

from . import access, selectors, storage, template_forms
from .constants import SEVERITIES, ActionStatus, CaseStatus
from .form_schema import FACTORS, QUESTIONS
from .forms import AssignmentForm, EvaluationForm, UploadForm
from .models import Attachment, Category, WorkflowPolicy
from .services import approvals
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
    if case.form_version >= 2:
        return form_transition_options(case, user, policy)
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
            access.control_review(case, request.user, confirm=True)
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
            and case.status
            in (
                {CaseStatus.PLANNING}
                if case.form_version >= 2
                else {CaseStatus.INVESTIGATING, CaseStatus.PLANNING}
            )
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
    extra = form_context(case, request.user, ctx) if case.form_version >= 2 else {}
    return render(
        request,
        "deviations/detail_v2.html"
        if case.form_version >= 2
        else "deviations/detail.html",
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
            and case.status
            in (
                {CaseStatus.INVESTIGATING}
                if case.form_version >= 2
                else {CaseStatus.INVESTIGATING, CaseStatus.PLANNING}
            )
            and bool(ctx["policy"] and ctx["policy"].enabled),
            "can_review": can_review,
            "can_evaluate": can_review and case.status == CaseStatus.VERIFYING,
            "transitions": transition_options(case, request.user, ctx["policy"]),
            "assignment_form": template_forms.AssignmentForm(instance=case)
            if case.form_version >= 2
            else AssignmentForm(
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
            **extra,
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
    if case.form_version >= 2:
        from .presentation import print_context

        return render(request, "deviations/print_v2.html", print_context(case))
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


def form_transition_options(case, user, policy):
    active = bool(policy and policy.enabled)
    manage = has_function(user, "deviations_manage") and (
        is_admin(user) or case.owner_id == user.pk
    )
    choices = []
    if (
        case.status in {CaseStatus.DRAFT, CaseStatus.NEEDS_INFO}
        and has_function(user, "deviations_create")
        and (is_admin(user) or case.created_by_id == user.pk)
    ):
        choices.append(("submit", "Gửi báo cáo duyệt", False))
    if active and manage:
        if case.status == CaseStatus.INVESTIGATING:
            choices.append(("plan", "Gửi điều tra duyệt", False))
        if case.status == CaseStatus.PLANNING:
            choices.extend(
                [
                    ("submit_capa", "Gửi kế hoạch CAPA duyệt", False),
                    ("restart_analysis", "Mở lại điều tra", True),
                ]
            )
        if case.status == CaseStatus.EXECUTING:
            choices.append(("request_evaluation", "Gửi đánh giá hiệu quả", False))
    if (
        active
        and case.status == CaseStatus.INVESTIGATING
        and (
            is_admin(user)
            or (
                case.control_reviewer_id == user.pk
                and has_function(user, "deviations_control_approve")
            )
        )
    ):
        choices.append(("request_report_correction", "Yêu cầu bổ sung báo cáo", True))
    if active and case.status == CaseStatus.CLOSED:
        try:
            access.control_review(case, user, confirm=True)
            choices.append(("reopen", "Mở lại hồ sơ", True))
        except (PermissionDenied, ValidationError):
            pass
    if (
        not case.is_terminal
        and case.status not in {CaseStatus.EXECUTING, CaseStatus.VERIFYING}
        and (
            is_admin(user)
            or (
                case.created_by_id == user.pk
                and case.status in {CaseStatus.DRAFT, CaseStatus.NEEDS_INFO}
                and has_function(user, "deviations_create")
            )
        )
    ):
        choices.append(("cancel", "Hủy hồ sơ có lý do", True))
    return [
        {"command": key, "label": label, "reason": reason, "review": key == "reopen"}
        for key, label, reason in choices
    ]


def form_context(case, user, ctx):
    from .presentation import decorate_runs, document

    runs = decorate_runs(
        list(
            case.approval_runs.select_related("created_by")
            .prefetch_related("decisions")
            .order_by("-pk")
        )
    )
    pending = next((run for run in runs if run.status == "PENDING"), None)
    proposed_classification = (
        pending.decisions.filter(decision="APPROVE")
        .order_by("-step")
        .values_list("classification", flat=True)
        .first()
        if pending and pending.stage == "ANALYSIS"
        else None
    )
    return {
        "classification_caption": "Loại đề xuất"
        if case.status
        in {
            CaseStatus.DRAFT,
            CaseStatus.REPORTED,
            CaseStatus.NEEDS_INFO,
            CaseStatus.INVESTIGATING,
            CaseStatus.ANALYSIS_REVIEW,
        }
        else "Loại đã duyệt",
        "report_document": document(case, "REPORT"),
        "analysis_document": document(case, "ANALYSIS"),
        "capa_document": document(case, "CAPA"),
        "can_assign": ctx["can_manage"]
        and not case.is_terminal
        and case.status != CaseStatus.DRAFT
        and (not pending or pending.stage == "REPORT"),
        "approval_runs": runs,
        "pending_run": pending,
        "can_decide": bool(
            ctx["policy"]
            and ctx["policy"].enabled
            and pending
            and approvals.can_decide(case, pending, user)
        ),
        "can_recall": bool(
            pending and (is_admin(user) or pending.created_by_id == user.pk)
        ),
        "approval_form": template_forms.ApprovalForm(
            initial={
                "revision": case.revision,
                "owner": case.owner_id,
                "classification": proposed_classification or case.severity,
            },
            allow_owner=bool(
                pending
                and pending.stage == "REPORT"
                and approvals.current_role(pending) == "control"
            ),
            allow_classification=bool(pending and pending.stage == "ANALYSIS"),
        ),
        "can_plan_actions": ctx["can_manage"]
        and (is_admin(user) or case.owner_id == user.pk)
        and case.status == CaseStatus.PLANNING
        and bool(ctx["policy"] and ctx["policy"].enabled),
        "questions": QUESTIONS,
        "factors": FACTORS,
    }


@login_required
@require_safe
def approval_print(request, pk, run_id):
    from .models import ApprovalRun
    from .presentation import print_context

    case = case_for(request.user, pk)
    run = get_object_or_404(
        ApprovalRun.objects.prefetch_related("decisions"), pk=run_id, case=case
    )
    return render(request, "deviations/print_v2.html", print_context(case, run))
