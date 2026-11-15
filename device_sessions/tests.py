from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.test import Client, TestCase
from django.utils import timezone

from .models import DeviceSession

PASSWORD = "mat-khau-thu-thiet-bi"
CHROME = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0 Safari/537.36"
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) Version/18.0 Mobile/15E148 Safari/604.1"


class DeviceSessionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user("nv_thiet_bi", password=PASSWORD)
        cls.other = User.objects.create_user("nv_khac", password=PASSWORD)
        cls.admin = User.objects.create_superuser("qt_thiet_bi", password=PASSWORD)

    def sign_in(self, user, agent):
        client = Client(HTTP_USER_AGENT=agent)
        response = client.post(
            "/login/", {"username": user.username, "password": PASSWORD}
        )
        self.assertEqual(response.status_code, 302)
        return client

    def test_login_records_device_and_logout_forgets_it(self):
        laptop = self.sign_in(self.staff, CHROME)
        row = DeviceSession.objects.get(user=self.staff)
        self.assertEqual(row.device, "Chrome trên Windows")
        self.assertEqual(row.session_key, laptop.session.session_key)
        laptop.post("/logout/")
        self.assertFalse(DeviceSession.objects.filter(user=self.staff).exists())

    def test_user_logs_out_another_device_remotely(self):
        laptop = self.sign_in(self.staff, CHROME)
        phone = self.sign_in(self.staff, IPHONE)
        page = laptop.get("/account/devices/")
        self.assertContains(page, "Chrome trên Windows")
        self.assertContains(page, "Safari trên iPhone/iPad")
        self.assertContains(page, "Thiết bị này")
        phone_row = DeviceSession.objects.get(device="Safari trên iPhone/iPad")
        laptop.post(f"/account/devices/{phone_row.pk}/logout/")
        # The phone's next request is anonymous; the laptop keeps working.
        self.assertEqual(phone.get("/account/devices/").status_code, 302)
        self.assertEqual(laptop.get("/account/devices/").status_code, 200)

    def test_cannot_touch_someone_elses_device(self):
        laptop = self.sign_in(self.staff, CHROME)
        self.sign_in(self.other, CHROME)
        foreign = DeviceSession.objects.get(user=self.other)
        response = laptop.post(f"/account/devices/{foreign.pk}/logout/")
        self.assertEqual(response.status_code, 404)
        self.assertTrue(DeviceSession.objects.filter(pk=foreign.pk).exists())
        self.assertNotContains(laptop.get("/account/devices/"), "nv_khac")

    def test_logout_all_other_devices_keeps_current(self):
        laptop = self.sign_in(self.staff, CHROME)
        phone = self.sign_in(self.staff, IPHONE)
        tablet = self.sign_in(self.staff, IPHONE)
        laptop.post("/account/devices/logout-others/")
        self.assertEqual(DeviceSession.objects.filter(user=self.staff).count(), 1)
        self.assertEqual(phone.get("/account/devices/").status_code, 302)
        self.assertEqual(tablet.get("/account/devices/").status_code, 302)
        self.assertEqual(laptop.get("/account/devices/").status_code, 200)

    def test_admin_signs_employee_out_everywhere(self):
        laptop = self.sign_in(self.staff, CHROME)
        phone = self.sign_in(self.staff, IPHONE)
        other = self.sign_in(self.other, CHROME)
        admin = self.sign_in(self.admin, CHROME)
        page = admin.get(f"/team/{self.staff.pk}/edit/")
        self.assertContains(page, "Đăng xuất khỏi mọi thiết bị")
        admin.post(f"/team/{self.staff.pk}/logout-everywhere/")
        for client in (laptop, phone):
            self.assertEqual(client.get("/account/devices/").status_code, 302)
        self.assertEqual(other.get("/account/devices/").status_code, 200)
        self.assertEqual(admin.get("/account/devices/").status_code, 200)

    def test_employee_cannot_sign_out_others(self):
        laptop = self.sign_in(self.staff, CHROME)
        target = self.sign_in(self.other, CHROME)
        response = laptop.post(f"/team/{self.other.pk}/logout-everywhere/")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(target.get("/account/devices/").status_code, 200)

    def test_existing_sessions_are_registered_lazily(self):
        client = Client(HTTP_USER_AGENT=CHROME)
        client.force_login(self.staff)  # no login signal with a request
        DeviceSession.objects.all().delete()
        client.get("/account/devices/")
        self.assertTrue(DeviceSession.objects.filter(user=self.staff).exists())

    def test_cleanup_removes_rows_of_expired_sessions(self):
        laptop = self.sign_in(self.staff, CHROME)
        Session.objects.filter(session_key=laptop.session.session_key).update(
            expire_date=timezone.now() - timedelta(seconds=1)
        )
        call_command("cleanup_device_sessions", stdout=StringIO())
        self.assertFalse(DeviceSession.objects.exists())

    def test_menu_link_for_every_signed_in_user(self):
        laptop = self.sign_in(self.staff, CHROME)
        self.assertContains(
            laptop.get("/account/password/"), 'href="/account/devices/"'
        )
