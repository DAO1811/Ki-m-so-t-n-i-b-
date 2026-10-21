from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .test_support import grant_functions


class ModuleNavigationTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            "module-admin", password="test"
        )
        self.reader = get_user_model().objects.create_user(
            "module-reader", password="test"
        )
        grant_functions(self.reader, ["products_view"])

    def test_admin_modules_and_separation(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("products"))
        modules = {m["key"]: m for m in response.context["navigation_modules"]}
        self.assertEqual(
            list(modules),
            ["warehouse", "processes", "human_resources", "administration"],
        )

        def links(key):
            return {i["url"] for g in modules[key]["sections"] for i in g["items"]}

        self.assertIn(reverse("products"), links("warehouse"))
        self.assertIn(reverse("custom_fields"), links("warehouse"))
        self.assertNotIn(reverse("team"), links("warehouse"))
        self.assertIn(reverse("team"), links("administration"))
        self.assertIn(reverse("drive_settings"), links("administration"))
        self.assertEqual(response.context["current_module"]["key"], "warehouse")
        response = self.client.get(reverse("team"))
        self.assertEqual(response.context["current_module"]["key"], "administration")
        self.assertNotContains(response, 'id="global-warehouse"')

    def test_placeholders_are_authenticated_read_only_and_do_not_grant_permissions(
        self,
    ):
        for route in ["processes", "human_resources"]:
            url = reverse(route)
            self.assertEqual(self.client.get(url).status_code, 302)
            self.client.force_login(self.reader)
            response = self.client.get(url)
            self.assertContains(response, "Chưa triển khai")
            self.assertEqual(response.context["current_module"]["key"], route)
            self.assertNotContains(response, 'id="global-warehouse"')
            self.assertNotContains(response, 'href="/team/"')
            self.assertNotContains(response, 'href="/settings/drive/"')
            self.assertIn(self.client.post(url).status_code, (403, 405))
            self.assertEqual(self.client.get(reverse("team")).status_code, 403)
            self.client.logout()

    def test_reader_keeps_only_existing_authorized_links(self):
        self.client.force_login(self.reader)
        response = self.client.get(reverse("products"))
        self.assertContains(response, 'href="/products/"')
        self.assertNotContains(response, 'href="/operations/in/"')
        self.assertNotContains(response, 'href="/approvals/"')
        self.assertContains(response, reverse("processes"))
        self.assertContains(response, reverse("human_resources"))
