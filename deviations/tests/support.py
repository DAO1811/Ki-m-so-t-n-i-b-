from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from deviations.models import Category, WorkflowPolicy
from deviations.services import actions, cases, policies, workflow
from inventory.test_support import grant_functions


class DeviationTestCase(TestCase):
    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser("sl-admin")
        self.maker = User.objects.create_user("sl-maker")
        self.manager = User.objects.create_user("sl-manager")
        self.worker = User.objects.create_user("sl-worker")
        self.reviewer = User.objects.create_user("sl-reviewer")
        self.reader = User.objects.create_user("sl-reader")
        grant_functions(self.maker, ["deviations_create"], level=10)
        grant_functions(self.manager, ["deviations_manage"], level=20)
        grant_functions(self.worker, ["deviations_work"], level=10)
        grant_functions(self.reviewer, ["deviations_review"], level=30)
        self.category, _ = Category.objects.get_or_create(name="Quy trình & tuân thủ")
        WorkflowPolicy.objects.get_or_create(pk=1)

    def payload(self, **overrides):
        return dict(
            title="Sai lệch bàn giao hồ sơ",
            category=self.category,
            department="Vận hành",
            location="",
            occurred_at=None,
            detected_at=timezone.now() - timedelta(minutes=2),
            actual="Thiếu chứng từ trong đợt bàn giao.",
            expected="Hồ sơ phải đầy đủ.",
            immediate_response="",
            impact="",
            estimated_loss=None,
            source_document=None,
            source_product=None,
            source_stocktake=None,
            **overrides,
        )

    def create(self, user=None):
        return cases.create_case(user or self.maker, self.payload())

    def enable(self, **overrides):
        data = dict(
            enabled=True,
            minimum_review_level=30,
            independent_review=True,
            require_higher_level=True,
            max_extensions=1,
        )
        data.update(overrides)
        return policies.update_policy(
            self.admin,
            data,
            WorkflowPolicy.objects.get(pk=1).revision,
            "Quy tắc giả lập chỉ dùng kiểm thử",
        )

    def step(self, case, command, user=None, **kwargs):
        case.refresh_from_db()
        return workflow.transition(
            case.pk, user or self.admin, case.revision, command, **kwargs
        )

    def investigating(self, maker=None):
        self.enable()
        case = self.create(maker)
        self.step(case, "submit", maker or self.maker)
        case.refresh_from_db()
        cases.assign_case(case.pk, self.admin, case.revision, self.manager)
        return self.step(case, "accept", self.manager)

    def planned(self, maker=None):
        case = self.investigating(maker)
        cases.save_analysis(
            case.pk,
            self.manager,
            case.revision,
            dict(
                findings="Đối chiếu thiếu hai hồ sơ.",
                direct_cause="Chưa bàn giao.",
                root_cause="Thiếu bước đối chiếu.",
                related_people="",
                severity="MAJOR",
                impact="Hồ sơ vận hành thiếu căn cứ.",
            ),
        )
        case = self.step(case, "plan", self.manager)
        action = actions.save_action(
            case.pk,
            self.manager,
            case.revision,
            dict(
                kind="CORRECTIVE",
                title="Bổ sung và đối chiếu hồ sơ",
                assignee=self.worker,
                collaborators="",
                due_date=timezone.localdate() + timedelta(days=2),
            ),
        )
        case.refresh_from_db()
        return case, action

    def executing(self):
        case, action = self.planned()
        return self.step(case, "approve_plan", self.reviewer), action

    def verifying(self):
        case, action = self.executing()
        actions.work_action(
            case.pk,
            self.worker,
            case.revision,
            action.pk,
            action.revision,
            "DONE",
            "Đã đối chiếu và đủ hồ sơ.",
        )
        return self.step(case, "request_evaluation", self.manager), action
