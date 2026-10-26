"""Readable report/approval projections; signature snapshots never use new profile names."""

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .constants import SEVERITIES, ActionKind
from .form_schema import (
    CONSEQUENCE,
    FACTORS,
    LIKELIHOOD,
    QUESTIONS,
    ROLES,
    STAGE_LABELS,
    risk_band,
)
from .services.approvals import chain_roles, payload
from .services.form_data import display_name


def moment(value):
    if not value:
        return "Chưa xác định"
    stamp = parse_datetime(value) if isinstance(value, str) else value
    return timezone.localtime(stamp).strftime("%d/%m/%Y %H:%M") if stamp else str(value)


def decorate_runs(runs):
    ids = {pk for run in runs for pk in run.participants.values()}
    people = {
        u.pk: display_name(u) for u in get_user_model().objects.filter(pk__in=ids)
    }
    for run in runs:
        decisions = {decision.step: decision for decision in run.decisions.all()}
        run.stage_label = STAGE_LABELS[run.stage]
        run.steps = [
            {
                "number": i,
                "label": run.labels.get("role_labels", {}).get(role, ROLES[role][0]),
                "assigned": people.get(
                    run.participants.get(role), "Tài khoản không còn hoạt động"
                ),
                "decision": decisions.get(i),
                "current": run.status == "PENDING" and run.current_step == i,
            }
            for i, role in enumerate(chain_roles(run), 1)
        ]
        role = chain_roles(run)[run.current_step - 1]
        run.current_role_label = run.labels.get("role_labels", {}).get(
            role, ROLES[role][0]
        )
    return runs


def document(case, stage, run=None):
    data = run.payload if run else payload(case, stage)
    result = {
        "evidence": data.get("_evidence", []),
        "stage": stage,
        "title": STAGE_LABELS[stage],
        "data": data,
        "run": run,
        "department": run.labels.get("department", case.department)
        if run
        else case.department,
    }
    if stage == "REPORT":
        result["occurred"] = moment(data.get("occurred_at"))
        result["detected"] = moment(data.get("detected_at"))
        result["reported"] = moment(data.get("reported_at"))
    elif stage == "ANALYSIS":
        result["questions"] = [
            {"label": label, **data.get("investigation_5w1h", {}).get(key, {})}
            for key, label in QUESTIONS
        ]
        labels = {
            "RELATED": "Có liên quan",
            "EXCLUDED": "Đã loại trừ",
            "NA": "Không áp dụng",
            "": "Chưa đánh giá",
        }
        result["factors"] = [
            {
                "label": label,
                **data.get("cause_factors", {}).get(key, {}),
                "conclusion": labels.get(
                    data.get("cause_factors", {}).get(key, {}).get("status", ""),
                    "Chưa đánh giá",
                ),
            }
            for key, label in FACTORS
        ]
        score = (data.get("likelihood") or 0) * (data.get("consequence") or 0) or None
        result["proposed_severity_label"] = dict(SEVERITIES).get(
            data.get("severity", ""), "Chưa đánh giá"
        )
        decisions = list(run.decisions.all()) if run else []
        classification = decisions[-1].classification if decisions else ""
        result["final_severity_label"] = (
            dict(SEVERITIES).get(classification, "")
            if run and run.status == "APPROVED" and classification
            else ""
        )
        result["severity_label"] = dict(SEVERITIES).get(
            data.get("severity", ""), "Chưa đánh giá"
        )
        result["risk_scale"] = [
            {
                "number": n,
                "likelihood": label,
                "consequence": dict(CONSEQUENCE)[n],
                "likelihood_selected": data.get("likelihood") == n,
                "consequence_selected": data.get("consequence") == n,
            }
            for n, label in LIKELIHOOD
        ]
        result["score"] = score
        result["risk_level"] = risk_band(score)
    else:
        names = (
            run.labels.get("assignees", {})
            if run
            else {
                str(a.assignee_id): display_name(a.assignee)
                for a in case.actions.filter(round=case.round).select_related(
                    "assignee"
                )
            }
        )
        result["rows"] = [
            {
                **row,
                "kind_label": dict(ActionKind.choices).get(row["kind"], row["kind"]),
                "assignee_name": names.get(
                    str(row["assignee_id"]), str(row["assignee_id"])
                ),
                "code": f"CAPA-{case.created_at.year}-{case.pk:06d}-{row['id']:04d}",
            }
            for row in data.get("actions", [])
        ]
    return result


def print_context(case, run=None):
    if run:
        decorate_runs([run])
        docs = [document(case, run.stage, run)]
    else:
        docs = []
        for stage in ("REPORT", "ANALYSIS", "CAPA"):
            query = case.approval_runs.filter(stage=stage)
            if stage != "REPORT":
                query = query.filter(round=case.round)
            chosen = query.order_by("-pk").prefetch_related("decisions").first()
            # Only show signature stamps with the frozen document they actually approved.
            if chosen and chosen.status in {"APPROVED", "PENDING"}:
                decorate_runs([chosen])
                docs.append(document(case, stage, chosen))
            else:
                docs.append(document(case, stage))
    return {
        "case": case,
        "document_title": run.labels.get("case_title", case.title)
        if run
        else case.title,
        "documents": docs,
        "single_run": run,
        "work_actions": case.actions.select_related("case").order_by("round", "pk"),
        "evaluations": case.evaluations.select_related("checked_by").order_by("pk"),
        "attachments": case.attachments.select_related("file").defer("file__data"),
        "runs": case.approval_runs.order_by("-pk"),
    }
