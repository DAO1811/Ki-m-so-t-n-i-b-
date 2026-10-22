from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from deviations.models import (
    Action,
    Case,
    Evaluation,
    Event,
    Extension,
    PolicyEvent,
    WorkflowPolicy,
)
from deviations.services import actions, cases, policies, workflow
from inventory.models import Balance, Document, Movement, Product
from inventory.test_support import grant_functions

from .support import DeviationTestCase


class WorkflowTests(DeviationTestCase):
    def test_initial_reporting_works_without_assumed_review_rules(self):
        case = self.create()
        self.assertFalse(WorkflowPolicy.objects.get(pk=1).enabled)
        self.assertIsNone(case.occurred_at)
        self.step(case, "submit", self.maker)
        case.refresh_from_db()
        cases.assign_case(case.pk, self.admin, case.revision, self.manager)
        with self.assertRaises(ValidationError):
            self.step(case, "accept", self.admin)
        case.refresh_from_db()
        self.assertEqual(case.status, "REPORTED")
        self.assertEqual(case.policy_snapshot, {})

    def test_complete_cycle_failed_effectiveness_and_reopening_keep_history(self):
        original = [m.objects.count() for m in (Balance, Document, Movement, Product)]
        case, first_action = self.verifying()
        code = case.code
        workflow.evaluate(
            case.pk,
            self.reviewer,
            case.revision,
            criteria="Kiểm tra đủ hồ sơ và áp dụng đối chiếu.",
            result="Bước đối chiếu còn thiếu.",
            effective=False,
            checked_at=timezone.now(),
        )
        case.refresh_from_db()
        self.assertEqual((case.status, case.round), ("PLANNING", 2))
        with self.assertRaises(ValidationError):
            self.step(case, "approve_plan", self.reviewer)
        second = actions.save_action(
            case.pk,
            self.manager,
            case.revision,
            dict(
                kind="PREVENTIVE",
                title="Bổ sung đối chiếu độc lập",
                assignee=self.worker,
                collaborators="",
                due_date=timezone.localdate() + timedelta(days=1),
            ),
        )
        case = self.step(case, "approve_plan", self.reviewer)
        actions.work_action(
            case.pk,
            self.worker,
            case.revision,
            second.pk,
            second.revision,
            "DONE",
            "Đã áp dụng và kiểm tra đủ.",
        )
        case = self.step(case, "request_evaluation", self.manager)
        workflow.evaluate(
            case.pk,
            self.reviewer,
            case.revision,
            criteria="Kiểm tra thực hiện quy trình.",
            result="Đã đủ và đạt.",
            effective=True,
            checked_at=timezone.now(),
        )
        case.refresh_from_db()
        self.assertEqual(case.status, "CLOSED")
        self.assertIsNotNone(case.closed_at)
        with self.assertRaises(ValidationError):
            cases.save_analysis(case.pk, self.manager, case.revision, {})
        reopened = self.step(
            case, "reopen", self.reviewer, reason="Tái diễn, cần đối chiếu bổ sung"
        )
        self.assertEqual(
            (reopened.code, reopened.round, reopened.status), (code, 3, "INVESTIGATING")
        )
        self.assertEqual(Evaluation.objects.filter(case=case).count(), 2)
        first_action.refresh_from_db()
        self.assertEqual(first_action.status, "DONE")
        self.assertEqual(
            original,
            [m.objects.count() for m in (Balance, Document, Movement, Product)],
        )
        self.assertTrue(
            Event.objects.filter(case=case, after__evaluation_id__isnull=False).exists()
        )

    def test_stale_revision_replay_and_forbidden_state_rollback(self):
        case = self.create()
        revision = case.revision
        self.step(case, "submit", self.maker)
        count = Event.objects.count()
        for operation in [
            lambda: workflow.transition(case.pk, self.maker, revision, "submit"),
            lambda: cases.edit_case(case.pk, self.maker, revision, self.payload()),
        ]:
            with self.assertRaises(ValidationError):
                operation()
        self.assertEqual(count, Event.objects.count())
        case.refresh_from_db()
        with self.assertRaises(PermissionDenied):
            cases.edit_case(case.pk, self.maker, case.revision, self.payload())

    def test_unknown_command_and_wrong_owner_cannot_modify(self):
        case = self.investigating()
        grant_functions(self.reader, ["deviations_manage"])
        with self.assertRaises(PermissionDenied):
            self.step(case, "plan", self.reader)
        with self.assertRaises(ValidationError):
            self.step(case, "undefined", self.admin)

    def test_required_information_and_dates_are_checked(self):
        for key, value in [
            ("detected_at", timezone.now() + timedelta(days=1)),
            ("occurred_at", timezone.now()),
            ("estimated_loss", -1),
            ("actual", ""),
        ]:
            data = self.payload()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError):
                cases.create_case(self.maker, data)
        self.assertEqual(Case.objects.count(), 0)
        case = self.investigating()
        with self.assertRaises(ValidationError):
            self.step(case, "plan", self.manager)

    def test_needs_information_decline_duplicate_and_cancel_have_reasons(self):
        self.enable()
        case = self.create()
        self.step(case, "submit", self.maker)
        with self.assertRaises(ValidationError):
            self.step(case, "need_info")
        case = self.step(case, "need_info", reason="Thiếu căn cứ")
        data = self.payload()
        data["expected"] = "Đã bổ sung căn cứ."
        cases.edit_case(case.pk, self.maker, case.revision, data)
        self.step(case, "submit", self.maker)
        duplicate = self.create()
        self.step(duplicate, "submit", self.maker)
        self.step(duplicate, "duplicate", reason="Cùng sự việc", duplicate_of=case)
        with self.assertRaises(ValidationError):
            self.step(
                case, "duplicate", reason="Liên kết ngược", duplicate_of=duplicate
            )
        self.step(case, "decline", reason="Đã xác minh không phải sai lệch")
        draft = self.create()
        self.step(draft, "cancel", self.maker, reason="Ghi nhầm sự việc")
        self.assertTrue(Case.objects.filter(pk=draft.pk, status="CANCELLED").exists())

    def test_explicit_review_rank_independence_and_admin_warning(self):
        case, _ = self.planned(self.admin)
        with self.assertRaises(PermissionDenied):
            self.step(case, "approve_plan", self.reviewer)
        with self.assertRaises(ValidationError):
            self.step(case, "approve_plan", self.admin)
        case = self.step(case, "approve_plan", self.admin, confirm=True)
        self.assertTrue(case.events.last().after["admin_self_review_confirmed"])
        # A grant alone does not satisfy rank and independence.
        self.assertEqual(case.creator_level, 40)

    def test_assignee_cannot_review_independent_plan_even_at_sufficient_rank(self):
        case, _ = self.planned()
        grant_functions(self.worker, ["deviations_work", "deviations_review"], level=30)
        with self.assertRaises(PermissionDenied):
            self.step(case, "approve_plan", self.worker)

    def test_permissions_are_reloaded_after_revocation(self):
        case = self.create()
        grant_functions(self.maker, [])
        with self.assertRaises(PermissionDenied):
            self.step(case, "submit", self.maker)
        self.assertEqual(case.events.count(), 1)

    def test_unconfigured_policy_cannot_be_enabled_and_edits_are_versioned(self):
        with self.assertRaises(ValidationError):
            policies.update_policy(
                self.admin,
                dict(
                    enabled=True,
                    minimum_review_level=None,
                    independent_review=None,
                    require_higher_level=None,
                    max_extensions=None,
                ),
                1,
                "Chưa chốt",
            )
        case = self.investigating()
        pinned = case.policy_snapshot.copy()
        self.enable(minimum_review_level=40, max_extensions=0)
        case.refresh_from_db()
        self.assertEqual(case.policy_snapshot, pinned)
        self.assertEqual(PolicyEvent.objects.count(), 2)
        with self.assertRaises(ValidationError):
            policies.update_policy(self.admin, dict(enabled=False), 1, "Bản cũ")
        with self.assertRaises(PermissionDenied):
            self.enable_as_reader()

    def enable_as_reader(self):
        return policies.update_policy(self.reader, {}, 1, "Không được phép")

    def test_assignment_requires_active_granted_account(self):
        case = self.create()
        self.step(case, "submit", self.maker)
        case.refresh_from_db()
        with self.assertRaises(ValidationError):
            cases.assign_case(case.pk, self.admin, case.revision, self.reader)
        self.manager.is_active = False
        self.manager.save()
        with self.assertRaises(ValidationError):
            cases.assign_case(case.pk, self.admin, case.revision, self.manager)

    def test_source_links_respect_permissions_and_dont_prevent_legacy_deletion(self):
        product = Product.objects.create(sku="SL-LINK", name="Hàng giả lập", unit="Cái")
        data = self.payload()
        data["source_product"] = product
        with self.assertRaises(PermissionDenied):
            cases.create_case(self.maker, data)
        grant_functions(self.maker, ["deviations_create", "products_view"])
        case = cases.create_case(self.maker, data)
        old_pk = product.pk
        product.delete()
        case.refresh_from_db()
        self.assertIsNone(case.source_product_id)
        self.assertEqual(case.events.first().after["source_product"], str(old_pk))

    def test_action_updates_are_locked_to_current_round_owner_and_state(self):
        case, action = self.executing()
        with self.assertRaises(PermissionDenied):
            actions.work_action(
                case.pk,
                self.reader,
                case.revision,
                action.pk,
                action.revision,
                "DONE",
                "Giả mạo",
            )
        with self.assertRaises(ValidationError):
            actions.work_action(
                case.pk,
                self.worker,
                case.revision,
                action.pk,
                action.revision + 1,
                "DONE",
                "Bản cũ",
            )
        with self.assertRaises(ValidationError):
            self.step(case, "request_evaluation", self.manager)
        self.assertEqual(Action.objects.get(pk=action.pk).status, "OPEN")

    def test_extension_reject_keeps_due_approval_changes_once_and_enforces_limit(self):
        case, action = self.executing()
        old_due = action.due_date
        extension = actions.request_extension(
            case.pk,
            self.worker,
            case.revision,
            action.pk,
            action.revision,
            old_due + timedelta(days=1),
            "Chờ chứng từ",
        )
        action.refresh_from_db()
        case.refresh_from_db()
        self.assertEqual(action.due_date, old_due)
        with self.assertRaises(ValidationError):
            actions.work_action(
                case.pk,
                self.worker,
                case.revision,
                action.pk,
                action.revision,
                "DONE",
                "Đã đủ",
            )
        actions.decide_extension(
            case.pk, self.reviewer, case.revision, extension.pk, False, "Chưa đủ căn cứ"
        )
        case.refresh_from_db()
        action.refresh_from_db()
        self.assertEqual(action.due_date, old_due)
        approved = actions.request_extension(
            case.pk,
            self.worker,
            case.revision,
            action.pk,
            action.revision,
            old_due + timedelta(days=2),
            "Có bổ sung căn cứ",
        )
        case.refresh_from_db()
        actions.decide_extension(
            case.pk, self.reviewer, case.revision, approved.pk, True, "Đã kiểm tra"
        )
        case.refresh_from_db()
        action.refresh_from_db()
        self.assertEqual(action.due_date, old_due + timedelta(days=2))
        with self.assertRaises(ValidationError):
            actions.request_extension(
                case.pk,
                self.worker,
                case.revision,
                action.pk,
                action.revision,
                old_due + timedelta(days=3),
                "Vượt hạn",
            )
        self.assertEqual(Extension.objects.filter(status="APPROVED").count(), 1)

    def test_extending_without_configured_limit_is_blocked(self):
        case, action = self.executing()
        case.policy_snapshot["max_extensions"] = None
        case.save(update_fields=["policy_snapshot"])
        with self.assertRaises(ValidationError):
            actions.request_extension(
                case.pk,
                self.worker,
                case.revision,
                action.pk,
                action.revision,
                action.due_date + timedelta(days=1),
                "Chưa chốt",
            )

    def test_future_evaluation_time_cannot_close_case(self):
        case, _ = self.verifying()
        with self.assertRaises(ValidationError):
            workflow.evaluate(
                case.pk,
                self.reviewer,
                case.revision,
                criteria="Đối chiếu",
                result="Đạt",
                effective=True,
                checked_at=timezone.now() + timedelta(days=1),
            )
        self.assertFalse(Evaluation.objects.exists())
        self.assertEqual(Case.objects.get(pk=case.pk).status, "VERIFYING")
