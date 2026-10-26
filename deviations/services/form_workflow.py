"""Template-v2 state machine. V1 dossiers keep their original workflow."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from deviations import access
from deviations.constants import CaseStatus as S
from inventory.access import is_admin

from . import approvals, form_data
from .common import reason_required, record, snapshot
from .policies import require_enabled


def transition_locked(case, user, command, reason="", confirm=False, **kwargs):
    from .cases import validate_report
    from .workflow import guard_actions

    user = approvals.lock_people(case, user)
    access.require_member(user)
    before = snapshot(case)
    if command == "submit":
        access.require(user, "deviations_create")
        if case.status not in {S.DRAFT, S.NEEDS_INFO} or (
            case.created_by_id != user.pk and not is_admin(user)
        ):
            raise PermissionDenied(
                "Chỉ người lập hoặc Admin được gửi nháp/phần bổ sung."
            )
        validate_report(case, user)
        form_data.report(case, complete=True)
        approvals.request_locked(case, user, "REPORT")
        case.status = S.REPORTED
        if not case.submitted_at:
            case.submitted_at = timezone.now()
    elif command == "plan":
        require_enabled()
        access.manage(case, user)
        if case.status != S.INVESTIGATING:
            raise ValidationError("Chỉ gửi điều tra khi đang xác minh.")
        form_data.investigation(case, complete=True)
        approvals.request_locked(case, user, "ANALYSIS")
        case.status = S.ANALYSIS_REVIEW
    elif command == "submit_capa":
        require_enabled()
        access.manage(case, user)
        if case.status != S.PLANNING:
            raise ValidationError("Chỉ gửi kế hoạch sau khi điều tra đã được duyệt.")
        latest = (
            case.approval_runs.filter(stage="ANALYSIS", round=case.round)
            .order_by("-pk")
            .first()
        )
        if not latest or latest.status != "APPROVED":
            raise ValidationError("Điều tra của lượt này chưa được xác nhận.")
        guard_actions(case)
        for action in case.actions.filter(round=case.round):
            form_data.action(action, complete=True)
        approvals.request_locked(case, user, "CAPA")
        case.status = S.PLAN_REVIEW
    elif command == "request_evaluation":
        require_enabled()
        access.manage(case, user)
        if case.status != S.EXECUTING:
            raise ValidationError("Hồ sơ chưa ở bước thực hiện.")
        guard_actions(case, completed=True)
        case.status = S.VERIFYING
    elif command == "reopen":
        require_enabled()
        access.control_review(case, user, confirm)
        if case.status != S.CLOSED:
            raise ValidationError("Chỉ mở lại hồ sơ đã kết thúc.")
        reason = reason_required(reason)
        case.round += 1
        case.closed_at = None
        case.status = S.INVESTIGATING
    elif command == "request_report_correction":
        require_enabled()
        access.require(user, "deviations_control_approve")
        if not is_admin(user) and case.control_reviewer_id != user.pk:
            raise PermissionDenied(
                "Chỉ KSNB được phân công hoặc Admin được yêu cầu sửa báo cáo."
            )
        if case.status != S.INVESTIGATING:
            raise ValidationError(
                "Chỉ yêu cầu bổ sung báo cáo khi đang điều tra, chưa gửi duyệt."
            )
        reason = reason_required(reason)
        case.approval_runs.filter(stage="REPORT", status="APPROVED").update(
            status="SUPERSEDED"
        )
        case.status = S.NEEDS_INFO
    elif command == "restart_analysis":
        require_enabled()
        access.manage(case, user)
        if case.status != S.PLANNING:
            raise ValidationError("Chỉ mở lại điều tra trước khi gửi kế hoạch.")
        reason = reason_required(reason)
        case.approval_runs.filter(
            stage="ANALYSIS", round=case.round, status="APPROVED"
        ).update(status="SUPERSEDED")
        case.status = S.INVESTIGATING
    elif command == "cancel":
        if case.is_terminal or case.status in {S.EXECUTING, S.VERIFYING}:
            raise ValidationError("Không hủy hồ sơ ở bước này.")
        if not is_admin(user) and (
            case.created_by_id != user.pk or case.status not in {S.DRAFT, S.NEEDS_INFO}
        ):
            raise PermissionDenied("Sau khi gửi, chỉ Admin được hủy hồ sơ có lý do.")
        reason = reason_required(reason)
        case.approval_runs.filter(status="PENDING").update(
            status="RETURNED", finished_at=timezone.now()
        )
        case.status = S.CANCELLED
    else:
        raise ValidationError(
            "Biểu mẫu mới yêu cầu xác nhận tuần tự; dùng thao tác tại phiếu đang chờ."
        )
    return record(
        case,
        user,
        {
            "submit": "Gửi báo cáo theo mẫu",
            "plan": "Gửi duyệt điều tra",
            "submit_capa": "Gửi duyệt CAPA",
            "request_evaluation": "Gửi đánh giá hiệu quả",
            "reopen": "Mở lại hồ sơ",
            "restart_analysis": "Mở lại điều tra",
            "request_report_correction": "Yêu cầu bổ sung báo cáo",
            "cancel": "Hủy hồ sơ",
        }.get(command, command),
        before,
        reason,
    )
