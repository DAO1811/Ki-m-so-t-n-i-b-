from copy import deepcopy
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from deviations import storage
from deviations.form_schema import FACTORS, PARTICIPANTS, QUESTIONS, risk_band
from deviations.models import Action, ApprovalDecision, ApprovalRun, Case
from deviations.services import actions, approvals, cases, workflow
from inventory.models import Balance, Document, Movement, Product
from inventory.test_support import grant_functions

from .support import DeviationTestCase
from .test_http_storage import image_file


class CompanyFormFixtures:
    def setup_roles(self):
        self.department = get_user_model().objects.create_user("form-department")
        self.specialist = get_user_model().objects.create_user("form-specialist")
        self.related = get_user_model().objects.create_user("form-related")
        self.control = get_user_model().objects.create_user("form-control")
        self.director = get_user_model().objects.create_user("form-director")
        for user, role in [
            (self.department, "department"),
            (self.specialist, "specialist"),
            (self.related, "related"),
            (self.control, "control"),
            (self.director, "director"),
        ]:
            grant_functions(user, [f"deviations_{role}_approve"], level=30)
        DeviationTestCase.enable(self)

    def report_data(self):
        return {
            **DeviationTestCase.payload(self),
            "location": "Khu bàn giao",
            "reporter_job_title": "Nhân viên vận hành",
            "reported_at": timezone.now() - timedelta(minutes=1),
            "discoverer_name": "Người phát hiện giả lập",
            "discoverer_job_title": "Nhân viên",
            "what_changed": "Thiếu hồ sơ so với danh sách",
            "detection_method": "Kiểm đếm đối chiếu",
            "gap_analysis": "Thiếu 1 biên bản",
            "expected": "Đủ chứng từ",
            "immediate_response": "Đã thông báo TBP và tạm giữ hồ sơ",
            "department_reviewer": self.department,
            "control_reviewer": self.control,
        }

    def transition(self, case, command, user=None, **kwargs):
        case.refresh_from_db()
        return workflow.transition(
            case.pk, user or self.manager, case.revision, command, **kwargs
        )

    def decide(self, case, user, decision="APPROVE", reason="", confirm=False):
        case.refresh_from_db()
        run = case.approval_runs.get(status="PENDING")
        return approvals.decide(
            case.pk,
            user,
            case.revision,
            run.pk,
            decision,
            reason,
            confirm,
            classification=case.severity
            if run.stage == "ANALYSIS" and decision == "APPROVE"
            else "",
        )

    def report_pending(self):
        case = cases.create_case(self.maker, self.report_data())
        return self.transition(case, "submit", self.maker)

    def investigative(self):
        case = self.report_pending()
        self.decide(case, self.department)
        case.refresh_from_db()
        data = {key: getattr(case, key) for key in PARTICIPANTS}
        data["owner"] = self.manager
        cases.assign_participants(case.pk, self.admin, case.revision, data)
        self.decide(case, self.control)
        case.refresh_from_db()
        data = {key: getattr(case, key) for key in PARTICIPANTS}
        data.update(
            specialist_reviewer=self.specialist,
            related_reviewer=self.related,
            director_reviewer=self.director,
        )
        return cases.assign_participants(case.pk, self.admin, case.revision, data)

    def analysis_data(self):
        return dict(
            findings="Thiếu biên bản đã được xác minh",
            direct_cause="Chưa đưa vào bộ hồ sơ",
            root_cause="Thiếu bước đối chiếu độc lập",
            related_people="Bộ phận vận hành theo danh sách bàn giao",
            severity="CRITICAL",
            impact="Chậm đối chiếu",
            investigation_5w1h={
                key: {
                    "answer": "Trả lời đã xác minh " + key,
                    "evidence": "Biên bản đối chiếu " + key,
                }
                for key, _ in QUESTIONS
            },
            investigation_expected="Phải đủ hồ sơ",
            investigation_gap="Thiếu một biên bản",
            affected_steps="Bàn giao, đối chiếu",
            has_history=False,
            history_details="Đã kiểm tra lịch sử, chưa có sự việc tương tự",
            event_sequence="1. Nhận hồ sơ; 2. Đối chiếu; 3. Phát hiện thiếu",
            cause_factors={
                key: {
                    "status": "RELATED" if key == "method" else "EXCLUDED",
                    "details": "Căn cứ đã đối chiếu " + key,
                }
                for key, _ in FACTORS
            },
            five_whys=[
                {
                    "cause": "Thiếu hồ sơ",
                    "why1": "Chưa đối chiếu",
                    "why2": "Chưa có điểm kiểm soát",
                    "why3": "",
                    "why4": "",
                    "why5": "",
                }
            ],
            causal_factors="Thiếu kiểm soát dẫn đến bỏ sót",
            likelihood=2,
            consequence=2,
            risk_details="Đối chiếu tần suất và hậu quả theo hồ sơ",
        )

    def planning(self):
        case = self.investigative()
        cases.save_analysis(case.pk, self.manager, case.revision, self.analysis_data())
        self.transition(case, "plan")
        self.decide(case, self.specialist)
        return self.decide(case, self.control)

    def action_data(self):
        return dict(
            kind="COMBINED",
            title="Hoàn thiện đối chiếu bàn giao",
            assignee=self.worker,
            collaborators="",
            due_date=timezone.localdate() + timedelta(days=2),
            problem="Thiếu bước đối chiếu",
            corrective_action="Bổ sung biên bản",
            preventive_action="Thêm bước đối chiếu độc lập",
            responsible_department="Vận hành",
        )

    def capa_pending(self):
        case = self.planning()
        action = actions.save_action(
            case.pk, self.manager, case.revision, self.action_data()
        )
        return self.transition(case, "submit_capa"), action

    def executable(self):
        case, action = self.capa_pending()
        for user in (self.related, self.control, self.director):
            self.decide(case, user)
        case.refresh_from_db()
        return case, action


class CompanyFormTests(CompanyFormFixtures, DeviationTestCase):
    def setUp(self):
        super().setUp()
        self.setup_roles()

    def test_complete_chain_and_ksnb_closes_without_second_director_decision(self):
        before = [m.objects.count() for m in (Balance, Document, Movement, Product)]
        case, action = self.executable()
        self.assertEqual(case.status, "EXECUTING")
        self.assertEqual(case.form_version, 2)
        self.assertEqual(
            (case.risk_score, case.risk_level, case.severity), (4, "Thấp", "CRITICAL")
        )
        self.assertTrue(action.capa_code.startswith("CAPA-"))
        actions.work_action(
            case.pk,
            self.worker,
            case.revision,
            action.pk,
            action.revision,
            "DONE",
            "Đã đối chiếu đầy đủ",
        )
        case = self.transition(case, "request_evaluation")
        with self.assertRaises(PermissionDenied):
            workflow.evaluate(
                case.pk,
                self.director,
                case.revision,
                criteria="Đối chiếu",
                result="Đạt",
                effective=True,
                checked_at=timezone.now(),
            )
        workflow.evaluate(
            case.pk,
            self.control,
            case.revision,
            criteria="Kiểm tra đủ hồ sơ và điểm kiểm soát",
            result="Đã thực hiện có hiệu quả",
            effective=True,
            checked_at=timezone.now(),
        )
        case.refresh_from_db()
        self.assertEqual(case.status, "CLOSED")
        self.assertEqual(case.approval_runs.filter(status="APPROVED").count(), 3)
        self.assertEqual(ApprovalDecision.objects.count(), 7)
        self.client.force_login(self.reader)
        printed = self.client.get(reverse("deviation_print", args=[case.pk]))
        self.assertContains(printed, "Đã đối chiếu đầy đủ")
        signed_plan = case.approval_runs.get(stage="CAPA")
        self.assertNotContains(
            self.client.get(
                reverse("deviation_approval_print", args=[case.pk, signed_plan.pk])
            ),
            "Đã đối chiếu đầy đủ",
        )
        self.assertEqual(
            before, [m.objects.count() for m in (Balance, Document, Movement, Product)]
        )

    def test_ksnb_can_assign_investigator_at_report_acceptance(self):
        case = self.report_pending()
        self.decide(case, self.department)
        case.refresh_from_db()
        run = case.approval_runs.get(status="PENDING")
        result = approvals.decide(
            case.pk, self.control, case.revision, run.pk, "APPROVE", owner=self.manager
        )
        self.assertEqual(
            (result.status, result.owner_id), ("INVESTIGATING", self.manager.pk)
        )
        self.client.force_login(self.department)
        for route in ("products", "stocktakes", "approvals"):
            self.assertEqual(self.client.get(reverse(route)).status_code, 403)

    def test_submitted_chain_order_survives_later_configuration_changes(self):
        from unittest.mock import patch

        from deviations.form_schema import CHAINS

        case = self.report_pending()
        run = case.approval_runs.get()
        self.assertEqual(run.labels["chain"], ["department", "control"])
        with patch.dict(CHAINS, {"REPORT": ("control", "department")}):
            self.decide(case, self.department)
            run.refresh_from_db()
            self.assertEqual(approvals.current_role(run), "control")

    def test_new_audit_stores_changes_and_keeps_signed_payload_complete(self):
        case = self.report_pending()
        run = case.approval_runs.get()
        self.decide(case, self.department)
        event = case.events.latest("pk")
        self.assertEqual(event.after["_format"], "delta-v2")
        self.assertNotIn("actual", event.after)
        self.assertEqual(run.payload["actual"], case.actual)
        legacy = self.create()
        self.step(legacy, "submit", self.maker)
        self.assertEqual(legacy.events.latest("pk").after["actual"], legacy.actual)

    def test_reviewers_choose_classification_without_rewriting_proposal(self):
        case = self.investigative()
        cases.save_analysis(case.pk, self.manager, case.revision, self.analysis_data())
        case = self.transition(case, "plan")
        run = case.approval_runs.get(status="PENDING")
        with self.assertRaises(ValidationError):
            approvals.decide(case.pk, self.specialist, case.revision, run.pk, "APPROVE")
        approvals.decide(
            case.pk,
            self.specialist,
            case.revision,
            run.pk,
            "APPROVE",
            reason="TBP đã đối chiếu phạm vi",
            classification="MAJOR",
        )
        case.refresh_from_db()
        self.assertEqual(case.severity, "CRITICAL")
        approvals.decide(
            case.pk,
            self.control,
            case.revision,
            run.pk,
            "APPROVE",
            reason="KSNB kết luận theo căn cứ",
            classification="MINOR",
        )
        case.refresh_from_db()
        run.refresh_from_db()
        self.assertEqual((case.severity, case.risk_score), ("MINOR", 4))
        self.assertEqual(run.payload["severity"], "CRITICAL")
        self.assertEqual(
            list(run.decisions.values_list("classification", flat=True)),
            ["MAJOR", "MINOR"],
        )

    def test_cannot_skip_department_or_reuse_v1_shortcuts(self):
        case = self.report_pending()
        with self.assertRaises(PermissionDenied):
            self.decide(case, self.control)
        for command in ("accept", "approve_plan", "return_plan"):
            with self.subTest(command=command), self.assertRaises(ValidationError):
                self.transition(case, command, self.admin, confirm=True)
        self.assertEqual(ApprovalDecision.objects.count(), 0)
        self.decide(case, self.department)
        case.refresh_from_db()
        self.assertEqual(case.status, "REPORTED")
        run = case.approval_runs.get()
        self.assertEqual(run.current_step, 2)

    def test_return_keeps_frozen_document_and_resubmission_starts_again(self):
        case = self.report_pending()
        first = case.approval_runs.get()
        initial = deepcopy(first.payload)
        self.decide(case, self.department)
        with self.assertRaises(ValidationError):
            self.decide(case, self.control, "RETURN")
        self.decide(case, self.control, "RETURN", "Bổ sung căn cứ")
        case.refresh_from_db()
        data = self.report_data()
        data["actual"] = "Nội dung bổ sung mới"
        data["title"] = "Tiêu đề mới"
        cases.edit_case(case.pk, self.maker, case.revision, data)
        self.transition(case, "submit", self.maker)
        first.refresh_from_db()
        self.assertEqual(first.payload, initial)
        self.assertEqual(first.status, "RETURNED")
        self.assertEqual(case.approval_runs.get(status="PENDING").current_step, 1)
        self.client.force_login(self.reader)
        response = self.client.get(
            reverse("deviation_approval_print", args=[case.pk, first.pk])
        )
        self.assertContains(response, initial["actual"])
        self.assertNotContains(response, "Nội dung bổ sung mới")

    def test_inactive_or_revoked_reviewer_cannot_sign(self):
        case = self.report_pending()
        grant_functions(self.department, [], level=30)
        with self.assertRaises(PermissionDenied):
            self.decide(case, self.department)
        self.assertEqual(ApprovalDecision.objects.count(), 0)
        self.department.is_active = False
        self.department.save()
        with self.assertRaises(PermissionDenied):
            self.decide(case, self.department)

    def test_admin_self_review_warning_and_takeover_reason_are_recorded(self):
        data = self.report_data()
        data.update(department_reviewer=self.admin, control_reviewer=self.admin)
        case = cases.create_case(self.admin, data)
        self.transition(case, "submit", self.admin)
        with self.assertRaises(ValidationError):
            self.decide(case, self.admin)
        self.decide(case, self.admin, confirm=True)
        decision = ApprovalDecision.objects.get()
        self.assertTrue(decision.self_confirmed)
        other = self.report_pending()
        with self.assertRaises(ValidationError):
            self.decide(other, self.admin)
        self.decide(other, self.admin, reason="Người được giao đang vắng", confirm=True)
        self.assertTrue(
            ApprovalDecision.objects.filter(
                run__case=other, admin_override=True
            ).exists()
        )

    def test_same_nonadmin_cannot_fill_two_roles_and_writer_cannot_self_sign(self):
        grant_functions(
            self.department,
            ["deviations_department_approve", "deviations_control_approve"],
            level=30,
        )
        data = self.report_data()
        data["control_reviewer"] = self.department
        case = cases.create_case(self.maker, data)
        with self.assertRaises(ValidationError):
            self.transition(case, "submit", self.maker)
        self.assertFalse(case.approval_runs.exists())

    def test_ksnb_can_request_report_correction_without_rewriting_old_signatures(self):
        case = self.investigative()
        old = case.approval_runs.get(stage="REPORT")
        original = deepcopy(old.payload)
        with self.assertRaises(PermissionDenied):
            self.transition(
                case, "request_report_correction", self.manager, reason="Kiểm tra lại"
            )
        case = self.transition(
            case,
            "request_report_correction",
            self.control,
            reason="Đối chiếu lại thời điểm và mô tả",
        )
        self.assertEqual(case.status, "NEEDS_INFO")
        old.refresh_from_db()
        self.assertEqual(old.status, "SUPERSEDED")
        self.assertEqual(old.payload, original)
        self.assertEqual(old.decisions.count(), 2)
        cases.edit_case(case.pk, self.maker, case.revision, self.report_data())
        self.transition(case, "submit", self.maker)
        self.assertEqual(case.approval_runs.get(status="PENDING").current_step, 1)

    def test_investigation_and_plan_cannot_edit_during_review(self):
        case = self.investigative()
        cases.save_analysis(case.pk, self.manager, case.revision, self.analysis_data())
        case = self.transition(case, "plan")
        with self.assertRaises(ValidationError):
            cases.save_analysis(
                case.pk, self.manager, case.revision, self.analysis_data()
            )
        with self.assertRaises(ValidationError):
            actions.save_action(
                case.pk, self.manager, case.revision, self.action_data()
            )
        self.decide(case, self.specialist)
        case = self.decide(case, self.control)
        with self.assertRaises(ValidationError):
            cases.save_analysis(
                case.pk, self.manager, case.revision, self.analysis_data()
            )

    def test_risk_bounds_and_fishbone_why_validation(self):
        case = self.investigative()
        data = self.analysis_data()
        data["likelihood"] = 6
        with self.assertRaises(ValidationError):
            cases.save_analysis(case.pk, self.manager, case.revision, data)
        data = self.analysis_data()
        data["five_whys"][0]["why2"] = ""
        data["five_whys"][0]["why3"] = "Bỏ bước"
        with self.assertRaises(ValidationError):
            cases.save_analysis(case.pk, self.manager, case.revision, data)
        data = self.analysis_data()
        data["cause_factors"]["people"]["details"] = ""
        cases.save_analysis(case.pk, self.manager, case.revision, data)
        with self.assertRaises(ValidationError):
            self.transition(case, "plan")
        self.assertEqual(
            [risk_band(n) for n in (None, 1, 4, 5, 9, 10, 25)],
            ["Chưa đánh giá", "Thấp", "Thấp", "Trung bình", "Trung bình", "Cao", "Cao"],
        )

    def test_capa_requires_all_three_steps_before_work(self):
        case, action = self.capa_pending()
        self.decide(case, self.related)
        self.decide(case, self.control)
        case.refresh_from_db()
        self.assertEqual(case.status, "PLAN_REVIEW")
        with self.assertRaises(ValidationError):
            actions.work_action(
                case.pk,
                self.worker,
                case.revision,
                action.pk,
                action.revision,
                "DONE",
                "Không được",
            )
        self.decide(case, self.director)
        case.refresh_from_db()
        self.assertEqual(case.status, "EXECUTING")

    def test_payload_tampering_and_stale_revisions_do_not_sign(self):
        case, action = self.capa_pending()
        rev = case.revision
        self.decide(case, self.related)
        with self.assertRaises(ValidationError):
            approvals.decide(
                case.pk,
                self.control,
                rev,
                case.approval_runs.get(status="PENDING").pk,
                "APPROVE",
            )
        Action.objects.filter(pk=action.pk).update(title="Nội dung khác bản đã gửi")
        with self.assertRaises(ValidationError):
            self.decide(case, self.control)
        self.assertEqual(ApprovalDecision.objects.filter(run__stage="CAPA").count(), 1)

    def test_recall_allows_reassignment_without_forging_a_decision(self):
        case = self.report_pending()
        run = case.approval_runs.get()
        approvals.recall(
            case.pk, self.maker, case.revision, run.pk, "Chọn lại người xác nhận"
        )
        case.refresh_from_db()
        self.assertEqual(case.status, "NEEDS_INFO")
        self.assertEqual(ApprovalDecision.objects.count(), 0)
        self.assertEqual(ApprovalRun.objects.get().status, "RETURNED")

    def test_failed_effectiveness_starts_new_investigation_round(self):
        case, action = self.executable()
        actions.work_action(
            case.pk,
            self.worker,
            case.revision,
            action.pk,
            action.revision,
            "DONE",
            "Đã làm",
        )
        case = self.transition(case, "request_evaluation")
        workflow.evaluate(
            case.pk,
            self.control,
            case.revision,
            criteria="Kiểm tra điểm kiểm soát",
            result="Chưa ngăn được lặp lại",
            effective=False,
            checked_at=timezone.now(),
        )
        case.refresh_from_db()
        self.assertEqual((case.status, case.round), ("INVESTIGATING", 2))
        self.assertEqual(
            case.approval_runs.filter(round=1, status="APPROVED").count(), 3
        )
        self.assertEqual(Action.objects.get(pk=action.pk).status, "DONE")

    @override_settings(DEBUG=True, PRIVATE_MEDIA_PROVIDER="database")
    def test_pending_review_freezes_evidence_and_keeps_snapshot_references(self):
        case = cases.create_case(self.maker, self.report_data())
        attachment = storage.add_attachment(
            case.pk,
            self.maker,
            case.revision,
            storage.validated_evidence(image_file()),
            "evidence.png",
            "Bằng chứng gốc",
        )
        case = self.transition(case, "submit", self.maker)
        run = case.approval_runs.get()
        self.assertEqual(run.payload["_evidence"][0]["id"], attachment.pk)
        self.assertFalse(storage.can_upload(case, self.maker))
        with self.assertRaises(ValidationError):
            storage.void_attachment(
                case.pk, self.admin, case.revision, attachment.pk, "Thử đổi"
            )

    def test_template_views_forms_prints_and_no_source_company_brand(self):
        case, action = self.capa_pending()
        self.client.force_login(self.admin)
        for name, args in [
            ("deviation_detail", [case.pk]),
            ("deviation_print", [case.pk]),
            ("deviation_approval_print", [case.pk, case.approval_runs.latest("pk").pk]),
        ]:
            response = self.client.get(reverse(name, args=args))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, "VNVC")
            self.assertNotContains(response, "SOP-QA")
        self.assertContains(
            self.client.get(reverse("deviation_detail", args=[case.pk])),
            "Tổng giám đốc",
        )
        self.client.force_login(self.reader)
        self.assertEqual(
            self.client.get(
                reverse(
                    "deviation_approval_print",
                    args=[case.pk, case.approval_runs.latest("pk").pk],
                )
            ).status_code,
            200,
        )
        response = self.client.post(
            reverse(
                "deviation_approval_decide",
                args=[case.pk, case.approval_runs.latest("pk").pk],
            ),
            {"revision": case.revision, "decision": "APPROVE"},
        )
        self.assertEqual(response.status_code, 403)

    def test_report_timestamp_is_business_time_not_submission_time(self):
        data = self.report_data()
        data["reported_at"] = data["detected_at"] - timedelta(minutes=1)
        with self.assertRaises(ValidationError):
            cases.create_case(self.maker, data)
        data = self.report_data()
        case = cases.create_case(self.maker, data)
        first = self.transition(case, "submit", self.maker)
        run = case.approval_runs.get()
        approvals.recall(case.pk, self.maker, first.revision, run.pk, "Bổ sung mô tả")
        second = self.transition(case, "submit", self.maker)
        self.assertEqual(second.submitted_at, first.submitted_at)
        self.assertLess(second.reported_at, second.submitted_at)


class FormMigrationTests(TransactionTestCase):
    def test_existing_cases_remain_v1_without_fabricated_dates_or_signatures(self):
        latest = MigrationExecutor(connection).loader.graph.leaf_nodes()
        target = [("deviations", "0003_category_revision")]
        try:
            executor = MigrationExecutor(connection)
            executor.migrate(target)
            apps = executor.loader.project_state(target).apps
            User = apps.get_model("auth", "User")
            OldCase = apps.get_model("deviations", "Case")
            Category = apps.get_model("deviations", "Category")
            actor = User.objects.create(
                username="legacy-form-owner", password="preserve-hash"
            )
            group = Category.objects.create(name="Nhóm giữ nguyên")
            record = OldCase.objects.create(
                title="Hồ sơ cũ đã kết thúc",
                category=group,
                department="Bộ phận cũ",
                actual="Nội dung cũ",
                created_by=actor,
                status="CLOSED",
                severity="MAJOR",
                root_cause="Nguyên nhân cũ",
            )
            MigrationExecutor(connection).migrate(latest)
            current = Case.objects.get(pk=record.pk)
            self.assertEqual(
                (
                    current.form_version,
                    current.status,
                    current.actual,
                    current.severity,
                ),
                (1, "CLOSED", "Nội dung cũ", "MAJOR"),
            )
            self.assertIsNone(current.reported_at)
            self.assertIsNone(current.likelihood)
            self.assertIsNone(current.control_reviewer_id)
            self.assertFalse(current.approval_runs.exists())
            # Simulate a still-running previous-version worker after DDL completes.
            rolling = OldCase.objects.create(
                title="Ghi từ worker cũ",
                category=group,
                department="Cũ",
                actual="Ghi trong lúc chuyển phiên bản",
                created_by=actor,
            )
            current_rolling = Case.objects.get(pk=rolling.pk)
            self.assertEqual(current_rolling.form_version, 1)
            self.assertEqual(current_rolling.investigation_5w1h, {})
            self.assertEqual(current_rolling.reporter_job_title, "")
        finally:
            MigrationExecutor(connection).migrate(latest)


class SerialApprovalConcurrencyTests(CompanyFormFixtures, TransactionTestCase):
    def setUp(self):
        DeviationTestCase.setUp(self)
        self.setup_roles()

    def test_two_clicks_cannot_approve_two_different_levels(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier

        from django.db import close_old_connections, connections

        if connection.vendor != "postgresql":
            self.skipTest("PostgreSQL row locks required")
        case = self.report_pending()
        run = case.approval_runs.get()
        gate = Barrier(2)

        def sign():
            close_old_connections()
            try:
                actor = get_user_model().objects.get(pk=self.department.pk)
                gate.wait(timeout=10)
                approvals.decide(case.pk, actor, case.revision, run.pk, "APPROVE")
                return "saved"
            except ValidationError:
                return "stale"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: sign(), range(2)))
        self.assertCountEqual(results, ["saved", "stale"])
        run.refresh_from_db()
        self.assertEqual(run.current_step, 2)
        self.assertEqual(ApprovalDecision.objects.filter(run=run).count(), 1)
