from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection, connections
from django.test import TransactionTestCase

from deviations.models import Case, Category, Event
from deviations.services import cases, workflow
from inventory.test_support import grant_functions


@skipUnless(connection.vendor == "postgresql", "Row-lock behavior requires PostgreSQL")
class ConcurrentCaseTests(TransactionTestCase):
    def setUp(self):
        self.maker = get_user_model().objects.create_user("concurrent-maker")
        self.admin = get_user_model().objects.create_superuser("concurrent-admin")
        grant_functions(self.maker, ["deviations_create"])
        self.category = Category.objects.create(name="Nhóm concurrency giả lập")
        self.case = Case.objects.create(
            title="Hồ sơ thử đồng thời",
            category=self.category,
            department="Vận hành",
            actual="Thiếu chứng từ",
            created_by=self.maker,
        )

    def race(self, operations):
        gate = Barrier(len(operations))

        def run(operation):
            close_old_connections()
            try:
                gate.wait(timeout=10)
                operation()
                return "saved"
            except ValidationError:
                return "stale"
            finally:
                # Test worker connections must close even with persistent connections.
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(operations)) as pool:
            return list(pool.map(run, operations))

    def test_two_submissions_post_exactly_once(self):
        def submit():
            maker = get_user_model().objects.get(pk=self.maker.pk)
            workflow.transition(self.case.pk, maker, 1, "submit")

        self.assertCountEqual(self.race([submit, submit]), ["saved", "stale"])
        self.assertEqual(Event.objects.filter(case=self.case).count(), 1)
        self.assertEqual(Case.objects.get(pk=self.case.pk).status, "REPORTED")

    def test_cancel_racing_submit_never_overwrites_newer_record(self):
        def submit():
            workflow.transition(
                self.case.pk,
                get_user_model().objects.get(pk=self.maker.pk),
                1,
                "submit",
            )

        def cancel():
            workflow.transition(
                self.case.pk,
                get_user_model().objects.get(pk=self.admin.pk),
                1,
                "cancel",
                reason="Ghi nhận nhầm",
            )

        self.assertCountEqual(self.race([submit, cancel]), ["saved", "stale"])
        self.assertEqual(Event.objects.filter(case=self.case).count(), 1)

    def test_two_edits_preserve_winning_revision_and_audit(self):
        from django.utils import timezone

        def edit(title):
            def operation():
                data = dict(
                    title=title,
                    category=self.category,
                    department="Vận hành",
                    location="",
                    occurred_at=None,
                    detected_at=timezone.now(),
                    actual="Thiếu chứng từ",
                    expected="",
                    immediate_response="",
                    impact="",
                    estimated_loss=None,
                    source_document=None,
                    source_product=None,
                    source_stocktake=None,
                )
                cases.edit_case(
                    self.case.pk,
                    get_user_model().objects.get(pk=self.maker.pk),
                    1,
                    data,
                )

            return operation

        self.assertCountEqual(
            self.race([edit("Chỉnh sửa A"), edit("Chỉnh sửa B")]), ["saved", "stale"]
        )
        self.case.refresh_from_db()
        self.assertEqual(self.case.revision, 2)
        self.assertEqual(
            Event.objects.get(case=self.case).after["title"], self.case.title
        )
