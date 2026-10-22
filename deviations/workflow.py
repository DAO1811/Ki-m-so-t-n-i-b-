"""One transition registry. Add/change a step here instead of branching in views."""

from dataclasses import dataclass

from .constants import CaseStatus as S


@dataclass(frozen=True)
class Transition:
    label: str
    sources: frozenset
    target: str
    permission: str
    guard: str = ""
    reason: bool = False
    review: bool = False


TRANSITIONS = {
    "submit": Transition(
        "Gửi ghi nhận",
        frozenset({S.DRAFT, S.NEEDS_INFO}),
        S.REPORTED,
        "deviations_create",
        "report",
    ),
    "accept": Transition(
        "Tiếp nhận & xác minh",
        frozenset({S.REPORTED}),
        S.INVESTIGATING,
        "deviations_manage",
        "accept",
    ),
    "need_info": Transition(
        "Yêu cầu bổ sung",
        frozenset({S.REPORTED, S.INVESTIGATING}),
        S.NEEDS_INFO,
        "deviations_manage",
        reason=True,
    ),
    "decline": Transition(
        "Không tiếp nhận",
        frozenset({S.REPORTED}),
        S.NOT_ACCEPTED,
        "deviations_manage",
        reason=True,
    ),
    "duplicate": Transition(
        "Đánh dấu hồ sơ trùng",
        frozenset({S.REPORTED}),
        S.DUPLICATE,
        "deviations_manage",
        "duplicate",
        reason=True,
    ),
    "plan": Transition(
        "Hoàn tất xác minh, lập kế hoạch",
        frozenset({S.INVESTIGATING}),
        S.PLANNING,
        "deviations_manage",
        "analysis",
    ),
    "approve_plan": Transition(
        "Xác nhận kế hoạch",
        frozenset({S.PLANNING}),
        S.EXECUTING,
        "deviations_review",
        "actions",
        review=True,
    ),
    "return_plan": Transition(
        "Yêu cầu bổ sung kế hoạch",
        frozenset({S.PLANNING}),
        S.INVESTIGATING,
        "deviations_review",
        reason=True,
        review=True,
    ),
    "request_evaluation": Transition(
        "Gửi đánh giá hiệu quả",
        frozenset({S.EXECUTING}),
        S.VERIFYING,
        "deviations_manage",
        "completed",
    ),
    "reopen": Transition(
        "Mở lại hồ sơ",
        frozenset({S.CLOSED}),
        S.INVESTIGATING,
        "deviations_review",
        reason=True,
        review=True,
    ),
    "cancel": Transition(
        "Hủy hồ sơ có lý do",
        frozenset({S.DRAFT, S.REPORTED, S.NEEDS_INFO, S.INVESTIGATING, S.PLANNING}),
        S.CANCELLED,
        "authenticated",
        reason=True,
    ),
}
