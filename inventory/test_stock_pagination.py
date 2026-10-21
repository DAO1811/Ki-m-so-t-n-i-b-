import csv
from io import StringIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .models import Balance, Document, Movement, Product, Warehouse
from .test_support import grant_functions


class StockPaginationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user("stock-page-reader")
        grant_functions(cls.user, {"stock_view", "ledger_view", "tools_export"})
        cls.a = Warehouse.objects.create(code="A", name="Warehouse A")
        cls.b = Warehouse.objects.create(code="B", name="Warehouse B")
        cls.hidden = Warehouse.objects.create(code="HIDDEN", name="Not authorized")
        cls.a.members.add(cls.user)
        cls.b.members.add(cls.user)
        products = Product.objects.bulk_create(
            [Product(sku=f"P{i:04}", name=f"Item{i}") for i in range(545)]
        )
        doc = Document.objects.create(
            kind="IN", destination=cls.a, status="POSTED", created_by=cls.user
        )
        Balance.objects.bulk_create(
            [
                Balance(
                    warehouse=cls.a if i < 500 else cls.b,
                    product=product,
                    quantity=1,
                    value=10,
                )
                for i, product in enumerate(products)
            ]
        )
        Movement.objects.bulk_create(
            [
                Movement(
                    document=doc,
                    warehouse=cls.a if i < 500 else cls.b,
                    product=product,
                    delta=1,
                    balance_after=1,
                    value_delta=10,
                    value_after=10,
                )
                for i, product in enumerate(products)
            ]
        )
        Balance.objects.create(
            warehouse=cls.hidden, product=products[0], quantity=99, value=990
        )
        Movement.objects.create(
            document=doc,
            warehouse=cls.hidden,
            product=products[0],
            delta=99,
            balance_after=99,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def test_all_545_stock_rows_are_reachable_without_exposing_other_warehouses(self):
        seen = []
        for page in range(1, 7):
            response = self.client.get(reverse("stock"), {"page": page})
            self.assertEqual(response.context["page_obj"].paginator.count, 545)
            seen.extend(row.pk for row in response.context["balances"])
            self.assertContains(response, "545 dòng tồn kho phù hợp")
            self.assertNotContains(response, "HIDDEN")
        self.assertEqual(len(seen), 545)
        self.assertEqual(len(set(seen)), 545)
        self.assertContains(response, "P0544")
        self.assertNotContains(response, "Hiển thị tối đa 500 dòng")

    def test_all_545_ledger_entries_are_reachable_with_stable_order_and_scope(self):
        seen = []
        for page in range(1, 7):
            response = self.client.get(reverse("ledger"), {"page": page})
            self.assertEqual(response.context["page_obj"].paginator.count, 545)
            seen.extend(row.pk for row in response.context["movements"])
            self.assertNotContains(response, "HIDDEN")
        self.assertEqual(len(seen), 545)
        self.assertEqual(len(set(seen)), 545)
        self.assertEqual(seen, sorted(seen, reverse=True))
        self.assertContains(response, "545 biến động phù hợp")

    def test_stock_filters_and_pagination_links_retain_full_selected_scope(self):
        response = self.client.get(
            reverse("stock"), {"warehouse": self.a.pk, "q": "Item"}
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 500)
        self.assertContains(response, f"warehouse={self.a.pk}&amp;q=Item&amp;page=2")
        response = self.client.get(
            reverse("stock"), {"warehouse": self.b.pk, "q": "Item5", "page": 9}
        )
        self.assertEqual(response.context["page_obj"].paginator.count, 45)
        self.assertEqual(len(response.context["balances"]), 45)
        self.assertContains(response, "P0544")
        self.assertEqual(
            self.client.get(
                reverse("stock"), {"warehouse": self.hidden.pk}
            ).status_code,
            404,
        )

    def test_csv_still_exports_every_authorized_row_beyond_first_page(self):
        for name in ("stock", "ledger"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name), {"export": 1, "page": 2})
                rows = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
                self.assertEqual(len(rows), 546)
                self.assertFalse(any("HIDDEN" in cell for row in rows for cell in row))
                self.assertTrue(any("P0544" in row for row in rows))
