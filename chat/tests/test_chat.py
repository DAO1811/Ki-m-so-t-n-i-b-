import io
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import close_old_connections, connection, transaction
from django.http import Http404
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from chat import calls, selectors, services
from chat.models import (
    Attachment,
    Call,
    CallMember,
    Member,
    Message,
    Reaction,
    Room,
    Signal,
)
from inventory.models import StoredFile
from inventory.test_support import grant_functions


@override_settings(DEBUG=True, PRIVATE_MEDIA_PROVIDER="database")
class ChatTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.a = User.objects.create_user("chat-a", first_name="An")
        self.b = User.objects.create_user("chat-b", first_name="Bình")
        self.c = User.objects.create_user("chat-c", first_name="Chi")
        self.admin = User.objects.create_superuser("chat-admin")
        self.blocked = User.objects.create_user("chat-no-rights")
        for user in [self.a, self.b, self.c]:
            grant_functions(user, ["chat_use", "chat_call", "chat_groups"])
        self.room = services.create_room(self.a, [self.b.pk])
        self.device_a, self.device_b = str(uuid4()), str(uuid4())

    def post(self, name, data, args=(), user=None):
        self.client.force_login(user or self.a)
        return self.client.post(
            reverse(name, args=args), json.dumps(data), content_type="application/json"
        )

    def msg(self, user=None, room=None, text="Xin chào", **kwargs):
        return services.send(
            user or self.a, (room or self.room).pk, text, uuid4(), **kwargs
        )

    def group(self, others=None):
        return services.create_room(self.a, others or [self.b.pk], "Vận hành", True)

    def start(self, room=None):
        return calls.start(
            self.a, (room or self.room).pk, "VIDEO", uuid4(), self.device_a
        )

    def image(self):
        output = io.BytesIO()
        Image.new("RGB", (10, 10), "yellow").save(output, "PNG")
        return SimpleUploadedFile(
            "anh.png", output.getvalue(), content_type="image/png"
        )

    def test_direct_creation_is_unique_and_requires_explicit_grants(self):
        self.assertEqual(services.create_room(self.b, [self.a.pk]).pk, self.room.pk)
        with self.assertRaises(PermissionDenied):
            services.create_room(self.a, [self.blocked.pk])
        with self.assertRaises(ValidationError):
            services.create_room(self.a, [])
        grant_functions(self.a, ["chat_use"])
        with self.assertRaises(PermissionDenied):
            self.group()

    def test_admin_cannot_read_or_send_in_unjoined_room(self):
        message = self.msg()
        self.client.force_login(self.admin)
        for name, args in [
            ("chat_room", [self.room.pk]),
            ("chat_messages", [self.room.pk]),
            ("chat_files", [self.room.pk]),
            ("chat_call_history", [self.room.pk]),
        ]:
            self.assertEqual(self.client.get(reverse(name, args=args)).status_code, 404)
        self.assertEqual(self.client.get(reverse("chat_summary")).json()["rooms"], [])
        with self.assertRaises(Http404):
            services.send(self.admin, self.room.pk, "Bí mật", uuid4())
        with self.assertRaises(Http404):
            services.react(self.admin, self.room.pk, message.pk, "👍")
        self.assertNotIn(
            Room, __import__("django.contrib.admin", fromlist=["site"]).site._registry
        )

    def test_ungranted_and_inactive_accounts_cannot_use_any_chat(self):
        self.client.force_login(self.blocked)
        self.assertEqual(self.client.get(reverse("chat_home")).status_code, 403)
        self.assertEqual(self.client.get(reverse("chat_summary")).status_code, 403)
        self.a.is_active = False
        self.a.save()
        with self.assertRaises(PermissionDenied):
            self.msg()

    def test_idempotent_send_preserves_one_message_and_checks_content(self):
        key = uuid4()
        first = services.send(self.a, self.room.pk, "Một tin", key)
        self.assertEqual(
            services.send(self.a, self.room.pk, "Một tin", key).pk, first.pk
        )
        self.assertEqual(Message.objects.count(), 1)
        with self.assertRaises(ValidationError):
            services.send(self.a, self.room.pk, "Nội dung khác", key)
        other = self.group()
        with self.assertRaises(ValidationError):
            services.send(self.a, other.pk, "Một tin", key)
        self.room.refresh_from_db()
        self.assertEqual(self.room.last_seq, 1)

    def test_stickers_and_emoji_do_not_allow_arbitrary_urls(self):
        message = self.msg(text="🌻 Xin chào 😄", sticker="lemon-01")
        self.assertEqual(message.sticker, "lemon-01")
        with self.assertRaises(ValidationError):
            self.msg(sticker="https://evil.invalid/tracker")
        with self.assertRaises(ValidationError):
            self.msg(text="x" * 4001)
        with self.assertRaises(ValidationError):
            self.msg(text="")
        self.assertTrue(self.msg(text="", sticker="cat-03").pk)

    def test_group_membership_old_history_quotes_and_files_are_private(self):
        group = self.group()
        prepared = services.prepare_uploads([self.image()])
        old = self.msg(room=group, text="Nội dung trước", uploads=prepared)
        services.manage_room(self.a, group.pk, "add", ids=[self.c.pk])
        new = self.msg(room=group, text="Mới", reply_id=old.pk)
        self.client.force_login(self.c)
        response = self.client.get(reverse("chat_messages", args=[group.pk])).json()
        self.assertEqual([m["id"] for m in response["messages"]], [str(new.pk)])
        self.assertNotIn("Nội dung trước", json.dumps(response, ensure_ascii=False))
        old_file = Attachment.objects.get(message=old)
        self.assertEqual(
            self.client.get(reverse("chat_file", args=[old_file.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.get(reverse("chat_files", args=[group.pk])).json()["files"], []
        )
        with self.assertRaises(ValidationError):
            self.msg(user=self.c, room=group, reply_id=old.pk)
        services.manage_room(self.a, group.pk, "remove", owner_id=self.c.pk)
        self.assertEqual(
            self.client.get(reverse("chat_messages", args=[group.pk])).status_code, 404
        )
        services.manage_room(self.a, group.pk, "add", ids=[self.c.pk])
        self.assertEqual(
            self.client.get(reverse("chat_messages", args=[group.pk])).json()[
                "messages"
            ],
            [],
        )

    def test_group_owner_is_not_overridden_by_admin_or_member(self):
        group = self.group([self.b.pk, self.admin.pk])
        with self.assertRaises(PermissionDenied):
            services.manage_room(self.admin, group.pk, "rename", title="Chiếm quyền")
        with self.assertRaises(PermissionDenied):
            services.manage_room(self.b, group.pk, "add", ids=[self.c.pk])
        with self.assertRaises(ValidationError):
            services.manage_room(self.a, group.pk, "leave")
        services.manage_room(self.a, group.pk, "owner", owner_id=self.b.pk)
        services.manage_room(self.a, group.pk, "leave")
        self.assertFalse(Member.objects.get(room=group, user=self.a).active)
        self.assertEqual(Room.objects.get(pk=group.pk).owner_id, self.b.pk)

    def test_private_attachments_cannot_use_warehouse_download_even_by_admin(self):
        prepared = services.prepare_uploads([self.image()])
        message = self.msg(uploads=prepared)
        attachment = Attachment.objects.get(message=message)
        self.assertEqual(attachment.file.context_key, "chat:" + str(self.room.pk))
        for user in [self.a, self.b]:
            self.client.force_login(user)
            response = self.client.get(reverse("chat_file", args=[attachment.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertEqual(response["Content-Type"], "image/jpeg")
            self.assertGreater(len(b"".join(response.streaming_content)), 0)
        self.client.force_login(self.admin)
        self.assertEqual(
            self.client.get(reverse("chat_file", args=[attachment.pk])).status_code, 404
        )
        self.assertEqual(
            self.client.get(
                reverse("private_file", args=[attachment.file_id])
            ).status_code,
            404,
        )

    def test_rejected_files_and_atomic_upload_failure(self):
        with self.assertRaises(ValidationError):
            services.prepare_uploads([SimpleUploadedFile("x.svg", b"<svg></svg>")])
        with self.assertRaises(ValidationError):
            services.prepare_uploads([SimpleUploadedFile("x.pdf", b"not a pdf")])
        with self.assertRaises(ValidationError):
            services.prepare_uploads([self.image()] * 4)
        with patch(
            "chat.services.store_file",
            side_effect=ValidationError("Drive indisponible"),
        ):
            with self.assertRaises(ValidationError):
                self.msg(uploads=services.prepare_uploads([self.image()]))
        self.assertEqual(Message.objects.count(), 0)
        self.room.refresh_from_db()
        self.assertEqual(self.room.last_seq, 0)

    def test_read_cursor_reply_reaction_and_removed_permission(self):
        first = self.msg()
        second = self.msg(self.b, text="Trả lời", reply_id=first.pk)
        services.react(self.a, self.room.pk, second.pk, "❤️")
        self.assertEqual(Reaction.objects.count(), 1)
        services.react(self.a, self.room.pk, second.pk, "❤️")
        self.assertEqual(Reaction.objects.count(), 0)
        services.mark_read(self.b, self.room.pk, first.seq)
        with self.assertRaises(ValidationError):
            services.mark_read(self.b, self.room.pk, 999)
        services.mark_read(self.b, self.room.pk, 0)
        self.assertEqual(
            Member.objects.get(room=self.room, user=self.b).read_seq, first.seq
        )
        grant_functions(self.b, [])
        self.client.force_login(self.b)
        self.assertEqual(
            self.client.get(reverse("chat_messages", args=[self.room.pk])).status_code,
            403,
        )
        with self.assertRaises(PermissionDenied):
            self.msg(self.b)

    def test_timeline_pagination_search_and_xss_are_scoped(self):
        for i in range(55):
            Message.objects.create(
                room=self.room,
                sender=self.a,
                seq=i + 1,
                client_key=uuid4(),
                text=f"Tin {i} <script>alert(1)</script>",
            )
        Room.objects.filter(pk=self.room.pk).update(last_seq=55)
        self.client.force_login(self.b)
        url = reverse("chat_messages", args=[self.room.pk])
        page = self.client.get(url).json()
        self.assertEqual(len(page["messages"]), 50)
        self.assertTrue(page["more"])
        older = self.client.get(url, {"before": page["messages"][0]["seq"]}).json()
        self.assertEqual(len(older["messages"]), 5)
        self.assertEqual(
            self.client.get(url, {"after": 50}).json()["messages"][0]["seq"], 51
        )
        search = self.client.get(url, {"q": "Tin 54"}).json()
        self.assertEqual(len(search["messages"]), 1)
        response = self.client.get(reverse("chat_room", args=[self.room.pk]))
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_csrf_is_required_for_send_and_api_anonymous_is_unauthorized(self):
        anon = Client()
        self.assertEqual(anon.get(reverse("chat_summary")).status_code, 401)
        strict = Client(enforce_csrf_checks=True)
        strict.force_login(self.a)
        response = strict.post(
            reverse("chat_send", args=[self.room.pk]),
            {"text": "No CSRF", "client_key": str(uuid4())},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(Message.objects.count(), 0)

    def test_video_call_invite_reject_and_private_signaling(self):
        call = self.start()
        self.assertEqual(call.status, "RINGING")
        with self.assertRaises(Http404):
            calls.act(self.admin, self.room.pk, call.pk, "join", uuid4())
        calls.act(self.b, self.room.pk, call.pk, "join", self.device_b)
        call.refresh_from_db()
        self.assertEqual(call.status, "ACTIVE")
        key = uuid4()
        sdp = {"type": "offer", "sdp": "v=0\r\n"}
        signal = calls.signal(
            self.a, self.room.pk, call.pk, self.b.pk, "OFFER", sdp, key, self.device_a
        )
        self.assertEqual(
            calls.signal(
                self.a,
                self.room.pk,
                call.pk,
                self.b.pk,
                "OFFER",
                sdp,
                key,
                self.device_a,
            ).pk,
            signal.pk,
        )
        self.assertEqual(
            len(
                calls.signals(self.b, self.room.pk, call.pk, device_key=self.device_b)[
                    1
                ]
            ),
            1,
        )
        self.assertEqual(
            calls.signals(self.a, self.room.pk, call.pk, device_key=self.device_a)[1],
            [],
        )
        with self.assertRaises(PermissionDenied):
            calls.signal(
                self.a,
                self.room.pk,
                call.pk,
                self.c.pk,
                "OFFER",
                sdp,
                uuid4(),
                self.device_a,
            )
        with self.assertRaises(PermissionDenied):
            calls.signal(
                self.a, self.room.pk, call.pk, self.b.pk, "OFFER", sdp, uuid4(), uuid4()
            )
        calls.act(self.b, self.room.pk, call.pk, "leave", self.device_b)
        call.refresh_from_db()
        self.assertEqual(call.status, "ENDED")
        self.assertEqual(Signal.objects.count(), 0)

    def test_call_membership_permission_and_second_tab_cannot_hijack(self):
        call = self.start()
        with self.assertRaises(ValidationError):
            calls.act(self.a, self.room.pk, call.pk, "join", uuid4())
        calls.act(self.b, self.room.pk, call.pk, "join", self.device_b)
        grant_functions(self.b, ["chat_use"])
        with self.assertRaises(PermissionDenied):
            calls.signals(self.b, self.room.pk, call.pk, device_key=self.device_b)
        grant_functions(self.b, ["chat_use", "chat_call"])
        with self.assertRaises(ValidationError):
            calls.act(self.b, self.room.pk, call.pk, "heartbeat", uuid4())

    def test_missed_call_expires_and_cannot_be_joined(self):
        call = self.start()
        Call.objects.filter(pk=call.pk).update(
            created_at=timezone.now() - timedelta(seconds=65)
        )
        Member.objects.filter(room=self.room).update(
            joined_at=timezone.now() - timedelta(seconds=120)
        )
        result = calls.act(self.b, self.room.pk, call.pk, "join", self.device_b)
        self.assertEqual(result.status, "ENDED")
        self.assertEqual(result.end_reason, "NO_ANSWER")

    def test_only_six_people_can_join_and_removed_member_stops_call(self):
        others = [self.b, self.c]
        for i in range(4):
            u = get_user_model().objects.create_user(f"call-peer-{i}")
            grant_functions(u, ["chat_use", "chat_call"])
            others.append(u)
        room = self.group([u.pk for u in others])
        call = self.start(room)
        for u in others[:5]:
            calls.act(u, room.pk, call.pk, "join", uuid4())
        with self.assertRaises(ValidationError):
            calls.act(others[5], room.pk, call.pk, "join", uuid4())
        self.assertEqual(
            CallMember.objects.filter(call=call, state="JOINED").count(), 6
        )
        services.manage_room(self.a, room.pk, "remove", owner_id=self.b.pk)
        self.assertEqual(CallMember.objects.get(call=call, user=self.b).state, "LEFT")
        with self.assertRaises(Http404):
            calls.signals(self.b, room.pk, call.pk, device_key=self.device_b)

    @override_settings(
        CHAT_TURN_URLS="turn:relay.example.test:3478",
        CHAT_TURN_SECRET="private-unit-test-secret",
    )
    def test_turn_tokens_are_ephemeral_and_never_expose_server_secret(self):
        servers = calls.ice_servers(self.a)
        self.assertNotIn("private-unit-test-secret", json.dumps(servers))
        self.assertEqual(len(servers), 2)
        self.assertGreater(
            int(servers[1]["username"].split(":")[0]), timezone.now().timestamp()
        )

    def test_bad_signal_and_call_rate_limits(self):
        with self.assertRaises(ValidationError):
            calls.signal_payload("OFFER", {"type": "answer", "sdp": "v=0"})
        with self.assertRaises(ValidationError):
            calls.signal_payload("ICE", {"candidate": "x", "sdpMLineIndex": -1})
        with self.assertRaises(ValidationError):
            calls.signal_payload(
                "ICE", {"candidate": "x", "url": "https://external.invalid"}
            )
        for i in range(30):
            Message.objects.create(
                room=self.room, sender=self.a, seq=i + 1, text="Thử", client_key=uuid4()
            )
        with self.assertRaises(ValidationError):
            self.msg()

    def test_sending_to_disabled_recipient_is_not_reported_as_delivered(self):
        self.b.is_active = False
        self.b.save()
        with self.assertRaises(ValidationError):
            self.msg()
        self.assertEqual(Message.objects.count(), 0)

    def test_unchanged_poll_is_small_and_does_not_bypass_revoked_permissions(self):
        message = self.msg(text="Nội dung riêng tư không lặp trong phản hồi rỗng")
        self.room.refresh_from_db()
        self.client.force_login(self.b)
        url = reverse("chat_messages", args=[self.room.pk])
        response = self.client.get(
            url, {"after": message.seq, "version": self.room.revision}
        )
        self.assertTrue(response.json()["unchanged"])
        self.assertNotIn(message.text, response.content.decode())
        self.assertLess(len(response.content), 1000)
        compact = self.client.get(
            reverse("chat_summary"), {"compact": 1, "rooms": 0}
        ).json()
        self.assertEqual(compact["rooms"], [])
        self.assertEqual(compact["unread"], 1)
        grant_functions(self.b, [])
        self.assertEqual(
            self.client.get(url, {"version": self.room.revision}).status_code, 403
        )

    def test_unread_counts_only_received_messages_and_not_fake_read_on_send(self):
        self.msg(text="A gửi")
        self.assertEqual(selectors.inbox(self.a)[0]["unread"], 0)
        self.assertEqual(selectors.unread_total(self.b), 1)
        self.msg(self.b, text="B chưa mở tin A")
        self.assertEqual(selectors.unread_total(self.b), 1)
        self.assertEqual(selectors.unread_total(self.a), 1)
        services.mark_read(self.b, self.room.pk, 2)
        self.assertEqual(selectors.unread_total(self.b), 0)

    def test_file_pagination_preserves_every_file_at_message_boundaries(self):
        stored = StoredFile.objects.create(
            sha256="0" * 64,
            context_key="chat:" + str(self.room.pk),
            content_type="application/pdf",
            size=0,
            data=b"",
        )
        ids = set()
        for i in range(12):
            m = Message.objects.create(
                room=self.room, sender=self.a, seq=i + 1, client_key=uuid4(), text="Tệp"
            )
            for j in range(3):
                ids.add(
                    str(
                        Attachment.objects.create(
                            message=m, file=stored, filename=f"ho-so-{i}-{j}.pdf"
                        ).pk
                    )
                )
        self.client.force_login(self.b)
        url = reverse("chat_files", args=[self.room.pk])
        one = self.client.get(url).json()
        self.assertEqual(len(one["files"]), 30)
        self.assertTrue(one["next"])
        two = self.client.get(url, {"before": one["next"]}).json()
        self.assertEqual({f["id"] for f in one["files"] + two["files"]}, ids)
        filtered = self.client.get(url, {"q": "ho-so-11-"}).json()
        self.assertEqual(len(filtered["files"]), 3)

    def test_chat_upload_uses_private_drive_chat_namespace(self):
        from inventory import drive
        from inventory.models import DriveConnection

        DriveConnection.objects.create(
            connected_by=self.admin,
            folder_id="root-preview",
            folder_name="Fake folder",
            account_email="preview@example.test",
            encrypted_refresh_token="mock",
        )
        parents = []

        def folder(token, parent, title, key):
            parents.append((parent, title, key))
            return "folder-" + str(len(parents))

        with (
            patch("inventory.drive.access_token", return_value="fake-token"),
            patch("inventory.drive.folder", side_effect=folder),
            patch(
                "inventory.drive.google_request",
                side_effect=[{"files": []}, {"id": "fake-file", "size": "3"}],
            ),
        ):
            with transaction.atomic():
                stored = drive.upload(
                    b"abc",
                    "image/jpeg",
                    "digest",
                    {
                        "kind": "chat",
                        "key": str(self.room.pk),
                        "name": "HoiThoai-test",
                        "year": "2026",
                    },
                    "anh.jpg",
                )
        self.assertEqual(stored, "fake-file")
        self.assertEqual(parents[0][1], "NhanTinNoiBo")
        self.assertEqual(len(parents), 3)


class ConcurrentChatTests(TransactionTestCase):
    def test_double_send_in_parallel_is_one_message(self):
        a = get_user_model().objects.create_user("parallel-a")
        b = get_user_model().objects.create_user("parallel-b")
        grant_functions(a, ["chat_use"])
        grant_functions(b, ["chat_use"])
        room = services.create_room(a, [b.pk])
        key = uuid4()
        barrier = Barrier(2)

        def submit():
            close_old_connections()
            try:
                user = get_user_model().objects.get(pk=a.pk)
                barrier.wait(timeout=10)
                return services.send(user, room.pk, "Chống gửi lặp", key).pk
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: submit(), range(2)))
        self.assertEqual(results[0], results[1])
        self.assertEqual(Message.objects.count(), 1)
        self.assertEqual(Room.objects.get(pk=room.pk).last_seq, 1)


class ChatUpgradeCompatibilityTests(TransactionTestCase):
    def test_upgrade_keeps_existing_password_permissions_catalog_and_balance(self):
        from django.core.management import call_command
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        from inventory.models import Balance, FunctionAccess, Product, Warehouse

        executor = MigrationExecutor(connection)
        old = [n for n in executor.loader.graph.leaf_nodes() if n[0] != "chat"] + [
            ("chat", None)
        ]
        try:
            executor.migrate(old)
            user = get_user_model().objects.create_user(
                "before-chat", password="local-test-only"
            )
            password = user.password
            grant_functions(user, ["products_view"])
            warehouse = Warehouse.objects.create(code="QA-OLD", name="Kho trước chat")
            warehouse.members.add(user)
            product = Product.objects.create(sku="QA-OLD", name="Hàng trước chat")
            balance = Balance.objects.create(
                warehouse=warehouse, product=product, quantity=7, value=140
            )
            call_command("safe_migrate", verbosity=0)
            user.refresh_from_db()
            balance.refresh_from_db()
            product.refresh_from_db()
            self.assertEqual(user.password, password)
            self.assertEqual(
                FunctionAccess.objects.get(user=user).permissions, ["products_view"]
            )
            self.assertTrue(warehouse.members.filter(pk=user.pk).exists())
            self.assertEqual((balance.quantity, balance.value), (7, 140))
            self.assertEqual(product.name, "Hàng trước chat")
            self.assertEqual(Room.objects.count(), 0)
            self.assertNotIn(
                "chat_use", FunctionAccess.objects.get(user=user).permissions
            )
        finally:
            restore = MigrationExecutor(connection)
            restore.migrate(restore.loader.graph.leaf_nodes())
