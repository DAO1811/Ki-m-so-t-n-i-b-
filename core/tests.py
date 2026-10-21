"""Authorization boundaries must survive moving views between company apps."""

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.test import TestCase, override_settings
from django.urls import include, path, resolve, reverse


def _unknown_view(module):
    @login_required
    def view(request):
        return HttpResponse("Unregistered function")

    view.__module__ = module + ".views"
    return view


urlpatterns = [
    path(module + "/", _unknown_view(module), name="unknown_" + module)
    for module in ("core", "inventory", "workflows", "people")
] + [path("", include("config.urls"))]


@override_settings(ROOT_URLCONF=__name__)
class FailClosedNamespaceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reader = get_user_model().objects.create_user("platform-reader")
        cls.admin = get_user_model().objects.create_superuser("platform-admin")

    def test_moving_a_view_to_a_company_app_does_not_bypass_authorization(self):
        self.client.force_login(self.reader)
        for module in ("core", "inventory", "workflows", "people"):
            with self.subTest(module=module):
                self.assertEqual(self.client.get("/" + module + "/").status_code, 403)

    def test_admin_retains_company_wide_access(self):
        self.client.force_login(self.admin)
        for module in ("core", "inventory", "workflows", "people"):
            with self.subTest(module=module):
                self.assertEqual(self.client.get("/" + module + "/").status_code, 200)


class PublicRouteCompatibilityTests(TestCase):
    def test_bookmarks_and_route_names_survive_app_separation(self):
        expected = {
            "team": ("/team/", "core.views"),
            "employee_new": ("/team/new/", "core.views"),
            "password_change": ("/account/password/", "core.views"),
            "processes": ("/processes/", "workflows.views"),
            "human_resources": ("/human-resources/", "people.views"),
            "products": ("/products/", "inventory.views.catalog"),
        }
        for name, (url, module) in expected.items():
            with self.subTest(name=name):
                self.assertEqual(reverse(name), url)
                self.assertEqual(resolve(url).func.__module__, module)
                self.assertEqual(self.client.get(url).status_code, 302)
