import json
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from chat import selectors, services
from chat.models import Member, Message, Room
from chat.stickers import STICKERS
from inventory.models import FunctionAccess
from inventory.test_support import grant_functions


class DirectoryTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.actor = User.objects.create_user("directory-owner", first_name="Ánh")
        self.person = User.objects.create_user(
            "dinh-dao",
            first_name="Đinh",
            last_name="Hữu Đạo",
            email="secret@example.test",
        )
        self.other = User.objects.create_user("binh", first_name="Bình")
        self.hidden = User.objects.create_user("not-granted", first_name="Đạo")
        self.inactive = User.objects.create_user("inactive", is_active=False)
        for user in [self.actor, self.person, self.other, self.inactive]:
            grant_functions(user, ["chat_use", "chat_groups"])
        FunctionAccess.objects.filter(user=self.person).update(
            job_title="Trưởng phòng kiểm soát"
        )
        self.client.force_login(self.actor)

    def test_contacts_require_permission_and_exclude_self_inactive_and_ungranted(self):
        response = self.client.get(reverse("chat_people"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {p["id"] for p in response.json()["people"]},
            {self.person.pk, self.other.pk},
        )
        self.assertNotIn("secret@example.test", response.content.decode())
        self.client.force_login(self.hidden)
        self.assertEqual(self.client.get(reverse("chat_people")).status_code, 403)
        self.assertEqual(self.client.get(reverse("chat_groups")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("chat_people")).status_code, 401)
        self.assertEqual(self.client.get(reverse("chat_groups")).status_code, 401)

    def test_search_ignores_vietnamese_accents_case_and_combines_name_tokens(self):
        for q in ["DINH DAO", "Đạo Hữu", "dinh-dao", "truong phong", "Đinh trưởng"]:
            people = self.client.get(reverse("chat_people"), {"q": q}).json()["people"]
            self.assertEqual([p["id"] for p in people], [self.person.pk], q)
        row = people[0]
        self.assertEqual(row["job_title"], "Trưởng phòng kiểm soát")
        self.assertEqual(set(row), {"id", "name", "username", "job_title"})

    def test_search_fields_do_not_match_unselected_fields(self):
        for field in ["name", "username", "job_title"]:
            result = self.client.get(
                reverse("chat_people"), {"q": "truong", "field": field}
            ).json()
            self.assertEqual(len(result["people"]), 1 if field == "job_title" else 0)
        result = self.client.get(
            reverse("chat_people"), {"q": "secret@example.test"}
        ).json()
        self.assertEqual(result["people"], [])

    def test_directory_pagination_keeps_every_eligible_user_without_duplicates(self):
        User = get_user_model()
        User.objects.bulk_create(
            [
                User(username=f"colleague-{n:03}", first_name=f"Đồng nghiệp {n:03}")
                for n in range(105)
            ]
        )
        FunctionAccess.objects.bulk_create(
            [
                FunctionAccess(user=u, permissions=["chat_use"])
                for u in User.objects.filter(username__startswith="colleague-")
            ]
        )
        offset, seen = 0, []
        while offset is not None:
            page = self.client.get(
                reverse("chat_people"),
                {"q": "dong nghiep", "offset": offset, "limit": 40},
            ).json()
            self.assertLessEqual(len(page["people"]), 40)
            seen.extend(p["id"] for p in page["people"])
            offset = page["next_offset"]
        self.assertEqual(len(seen), 105)
        self.assertEqual(len(set(seen)), 105)
        page = self.client.get(reverse("chat_people"), {"q": "nghiep 104"}).json()
        self.assertEqual(page["people"][0]["username"], "colleague-104")

    def test_invalid_directory_params_are_bounded(self):
        for route in ["chat_people", "chat_groups"]:
            for params in [
                {"offset": -1},
                {"offset": 100001},
                {"offset": "oops"},
                {"limit": 101},
                {"limit": 0},
                {"field": "email"},
            ]:
                self.assertEqual(
                    self.client.get(reverse(route), params).status_code, 400
                )

    def test_group_directory_only_returns_joined_groups_even_for_admin(self):
        group = services.create_room(
            self.actor, [self.person.pk, self.other.pk], "Điều hành miền Nam", True
        )
        private = services.create_room(self.person, [self.other.pk], "Riêng tư", True)
        services.create_room(self.actor, [self.person.pk])
        page = self.client.get(reverse("chat_groups"), {"q": "dieu NAM"}).json()
        self.assertEqual(len(page["groups"]), 1)
        self.assertEqual(page["groups"][0]["id"], str(group.pk))
        self.assertEqual(page["groups"][0]["member_count"], 3)
        self.assertNotIn(str(private.pk), json.dumps(page))
        Member.objects.filter(room=group, user=self.other).update(active=False)
        self.assertEqual(
            self.client.get(reverse("chat_groups")).json()["groups"][0]["member_count"],
            2,
        )
        self.client.force_login(self.other)
        groups = self.client.get(reverse("chat_groups")).json()["groups"]
        self.assertEqual([g["id"] for g in groups], [str(private.pk)])
        admin = get_user_model().objects.create_superuser("directory-admin")
        self.client.force_login(admin)
        self.assertEqual(self.client.get(reverse("chat_groups")).json()["groups"], [])

    def test_group_pagination_has_no_private_groups_or_duplicates(self):
        for n in range(7):
            services.create_room(self.actor, [self.person.pk], f"Nhóm số {n}", True)
        a = self.client.get(reverse("chat_groups"), {"q": "nhom", "limit": 4}).json()
        b = self.client.get(
            reverse("chat_groups"),
            {"q": "nhom", "limit": 4, "offset": a["next_offset"]},
        ).json()
        self.assertIsNone(b["next_offset"])
        self.assertEqual(len({g["id"] for g in a["groups"] + b["groups"]}), 7)
        self.assertEqual(Room.objects.count(), 7)

    def test_fun_stickers_are_fixed_safe_ids_and_keep_original_artwork(self):
        room = services.create_room(self.actor, [self.person.pk])
        self.assertEqual(len(STICKERS), 132)
        self.assertEqual(STICKERS["lemon-01"]["index"], 0)
        message = services.send(self.actor, room.pk, "", uuid4(), sticker="fun-01")
        member = room.members.get(user=self.actor)
        data = selectors.message_data(
            message, self.actor, member, list(room.members.all())
        )
        self.assertEqual(data["sticker"]["symbol"], "🤣")
        self.assertEqual(data["sticker"]["caption"], "Cười xỉu luôn!")
        self.assertEqual(Message.objects.count(), 1)
        home = self.client.get(reverse("chat_home"))
        self.assertContains(home, 'data-chat-view="contacts"')
        self.assertContains(home, "chat-directory.js")
