"""Frozen submissions and serial signatures; no step can skip its predecessor."""

import hashlib
import json

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from deviations import access
from deviations.constants import CaseStatus as S
from deviations.form_schema import (
    ACTION_EXTRA,
    ANALYSIS_EXTRA,
    CHAINS,
    REPORT_EXTRA,
    ROLES,
)
from deviations.models import ApprovalDecision, ApprovalRun
from inventory.access import has_function, is_admin
from inventory.hierarchy import approval_level

from . import form_data
from .common import active_actors, locked_case, reason_required, record, snapshot
from .policies import policy_snapshot, require_enabled

REPORT_CONTENT = (
    "title",
    "category_id",
    "department",
    "location",
    "occurred_at",
    "detected_at",
    "actual",
    "expected",
    "immediate_response",
    "impact",
    "estimated_loss",
    "reporter_name",
    "source_document_id",
    "source_product_id",
    "source_stocktake_id",
) + tuple(k for k in REPORT_EXTRA if not k.endswith("_reviewer"))
ANALYSIS_CONTENT = (
    "findings",
    "direct_cause",
    "root_cause",
    "related_people",
    "severity",
    "impact",
) + ANALYSIS_EXTRA


def serializable(value):
    return json.loads(json.dumps(value, default=str, ensure_ascii=False))


def payload(case, stage):
    data = _content(case, stage)
    if stage != "REPORT":
        data["_report_approval"] = (
            case.approval_runs.filter(stage="REPORT", status="APPROVED")
            .order_by("-pk")
            .values_list("pk", flat=True)
            .first()
        )
    if stage == "CAPA":
        data["_analysis_approval"] = (
            case.approval_runs.filter(
                stage="ANALYSIS", round=case.round, status="APPROVED"
            )
            .order_by("-pk")
            .values_list("pk", flat=True)
            .first()
        )
    data["_evidence"] = list(
        case.attachments.filter(voided_at__isnull=True).values(
            "id", "filename", "description", "file__sha256"
        )
    )
    return data


def _content(case, stage):
    if stage == "REPORT":
        return serializable({key: getattr(case, key) for key in REPORT_CONTENT})
    if stage == "ANALYSIS":
        return serializable({key: getattr(case, key) for key in ANALYSIS_CONTENT})
    fields = (
        "id",
        "round",
        "kind",
        "title",
        "assignee_id",
        "collaborators",
        "due_date",
    ) + ACTION_EXTRA
    return {
        "actions": [
            serializable({key: getattr(a, key) for key in fields})
            for a in case.actions.filter(round=case.round).order_by("pk")
        ]
    }


def fingerprint(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def lock_people(case, user, extra=()):
    people = [user, case.created_by, case.owner, *extra]
    people.extend(getattr(case, ROLES[r][1]) for r in ROLES)
    actors = active_actors(*people)
    case.created_by = actors[case.created_by_id]
    if case.owner_id:
        case.owner = actors[case.owner_id]
    for _, field, _ in ROLES.values():
        person_id = getattr(case, field + "_id")
        if person_id:
            setattr(case, field, actors[person_id])
    return actors[user.pk]


def request_locked(case, user, stage):
    if case.approval_runs.filter(status="PENDING").exists():
        raise ValidationError("Hồ sơ còn một phiếu đang chờ xác nhận.")
    roles = CHAINS[stage]
    form_data.participants_valid(case, roles)
    data = payload(case, stage)
    cycle = (
        case.approval_runs.filter(stage=stage, round=case.round).aggregate(
            n=Max("cycle")
        )["n"]
        or 0
    ) + 1
    return ApprovalRun.objects.create(
        case=case,
        stage=stage,
        round=case.round,
        cycle=cycle,
        participants={role: getattr(case, ROLES[role][1] + "_id") for role in roles},
        payload=data,
        labels={
            "chain": list(roles),
            "role_labels": {role: ROLES[role][0] for role in roles},
            "department": case.department,
            "case_title": case.title,
            "category": case.category.name,
            "assignees": {
                str(a.assignee_id): form_data.display_name(a.assignee)
                for a in case.actions.filter(round=case.round).select_related(
                    "assignee"
                )
            },
        },
        fingerprint=fingerprint(data),
        created_by=user,
        proposer_level=approval_level(user),
        proposer_name=form_data.display_name(user),
        proposer_job_title=form_data.job_title(user),
    )


def chain_roles(run):
    return tuple(run.labels.get("chain") or CHAINS[run.stage])


def current_role(run):
    return chain_roles(run)[run.current_step - 1]


def can_decide(case, run, user):
    if not run or run.status != "PENDING":
        return False
    role = current_role(run)
    return is_admin(user) or (
        run.participants.get(role) == user.pk and form_data.role_allowed(user, role)
    )


@transaction.atomic
def decide(
    pk,
    user,
    revision,
    run_id,
    decision,
    reason="",
    confirm=False,
    owner=None,
    classification="",
):
    case = locked_case(pk, revision)
    run = ApprovalRun.objects.select_for_update().get(pk=run_id, case=case)
    user = lock_people(case, user, [run.created_by, owner])
    policy = require_enabled()
    if case.form_version < 2 or run.status != "PENDING" or run.round != case.round:
        raise ValidationError(
            "Phiếu đã đổi lượt / đã có quyết định. Tải lại trước khi duyệt."
        )
    expected = {
        "REPORT": S.REPORTED,
        "ANALYSIS": S.ANALYSIS_REVIEW,
        "CAPA": S.PLAN_REVIEW,
    }[run.stage]
    if (
        case.status != expected
        or fingerprint(payload(case, run.stage)) != run.fingerprint
    ):
        raise ValidationError(
            "Nội dung đã thay đổi so với bản gửi. Rút phiếu để kiểm tra và gửi lại."
        )
    if decision not in {"APPROVE", "RETURN"}:
        raise ValidationError("Quyết định không hợp lệ.")
    role = current_role(run)
    if not can_decide(case, run, user):
        raise PermissionDenied(
            "Chỉ người được phân công ở bước hiện tại hoặc Admin được xác nhận; không được duyệt vượt cấp."
        )
    if not case.policy_snapshot:
        case.policy_snapshot = {
            **policy_snapshot(policy),
            "template_version": 2,
            "approval_chain_version": 1,
        }
    prior = list(run.decisions.values_list("actor_id", flat=True))
    if not is_admin(user) and user.pk == run.created_by_id:
        raise PermissionDenied("Người gửi không được tự duyệt phiếu của mình.")
    access.review_as(
        case,
        user,
        ROLES[role][2],
        confirm,
        extra_people=[run.created_by_id, *prior],
        proposer_level=max(run.proposer_level, approval_level(run.created_by)),
    )
    override = is_admin(user) and run.participants[role] != user.pk
    if decision == "RETURN" or override:
        reason = reason_required(reason)
    if run.stage == "ANALYSIS" and decision == "APPROVE":
        if classification not in {"MINOR", "MAJOR", "CRITICAL"}:
            raise ValidationError(
                "Cấp duyệt cần chọn phân loại sai lệch; hệ thống không tự quyết định theo RIV."
            )
        prior_type = run.decisions.filter(decision="APPROVE").order_by(
            "-step"
        ).values_list("classification", flat=True).first() or run.payload.get(
            "severity"
        )
        if classification != prior_type:
            reason = reason_required(reason)
    elif decision == "RETURN":
        classification = ""
    elif classification:
        raise ValidationError("Chỉ chọn phân loại khi đồng ý phiếu điều tra.")
    before = snapshot(case)
    if owner and not (
        run.stage == "REPORT" and role == "control" and decision == "APPROVE"
    ):
        raise ValidationError(
            "Chỉ phân công người phụ trách khi KSNB đồng ý tiếp nhận báo cáo."
        )
    if run.stage == "REPORT" and role == "control" and decision == "APPROVE":
        if owner:
            from django.contrib.auth import get_user_model

            case.owner = get_user_model().objects.get(pk=owner.pk)
        if not case.owner_id:
            case.owner = case.control_reviewer
        if (
            not case.owner
            or not case.owner.is_active
            or not has_function(case.owner, "deviations_manage")
        ):
            raise ValidationError(
                "Phân công người phụ trách có quyền quản lý hồ sơ trước khi KSNB tiếp nhận."
            )
    ApprovalDecision.objects.create(
        run=run,
        step=run.current_step,
        role=role,
        decision=decision,
        actor=user,
        actor_name=form_data.display_name(user),
        actor_job_title=form_data.job_title(user),
        reason=reason,
        admin_override=override,
        self_confirmed=bool(is_admin(user) and confirm),
        classification=classification,
    )
    if decision == "RETURN":
        run.status = "RETURNED"
        run.finished_at = timezone.now()
        case.status = {
            "REPORT": S.NEEDS_INFO,
            "ANALYSIS": S.INVESTIGATING,
            "CAPA": S.PLANNING,
        }[run.stage]
    elif run.current_step == len(chain_roles(run)):
        if run.stage == "ANALYSIS":
            case.severity = classification
        run.status = "APPROVED"
        run.finished_at = timezone.now()
        case.status = {
            "REPORT": S.INVESTIGATING,
            "ANALYSIS": S.PLANNING,
            "CAPA": S.EXECUTING,
        }[run.stage]
    else:
        run.current_step += 1
    run.save()
    return record(
        case,
        user,
        "Xác nhận theo biểu mẫu" if decision == "APPROVE" else "Không duyệt, trả lại",
        before,
        reason,
        {
            "approval_run": run.pk,
            "stage": run.stage,
            "role": role,
            "decision": decision,
            "admin_override": override,
            "admin_self_review_confirmed": bool(is_admin(user) and confirm),
        },
    )


@transaction.atomic
def recall(pk, user, revision, run_id, reason):
    case = locked_case(pk, revision)
    run = ApprovalRun.objects.select_for_update().get(pk=run_id, case=case)
    user = lock_people(case, user)
    access.require_member(user)
    if not is_admin(user) and (
        run.created_by_id != user.pk
        or not has_function(
            user, "deviations_create" if run.stage == "REPORT" else "deviations_manage"
        )
    ):
        raise PermissionDenied("Chỉ người gửi hoặc Admin được rút phiếu.")
    if run.status != "PENDING":
        raise ValidationError("Phiếu không còn chờ xác nhận.")
    reason = reason_required(reason)
    before = snapshot(case)
    run.status = "RETURNED"
    run.finished_at = timezone.now()
    run.save()
    case.status = {
        "REPORT": S.NEEDS_INFO,
        "ANALYSIS": S.INVESTIGATING,
        "CAPA": S.PLANNING,
    }[run.stage]
    return record(
        case, user, "Rút phiếu để bổ sung", before, reason, {"approval_run": run.pk}
    )
