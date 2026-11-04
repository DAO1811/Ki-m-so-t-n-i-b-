"""Room-serialized writes, idempotent sends and membership-scoped reads."""

import hashlib
from datetime import timedelta
from io import BytesIO
from pathlib import PurePath
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F
from django.http import Http404
from django.utils import timezone
from PIL import Image, ImageOps

from inventory.access import has_function
from inventory.media import store_file, validate_upload

from . import access
from .models import Attachment, Member, Message, Reaction, Room
from .stickers import STICKERS

EMOJI = ("👍", "❤️", "😂", "😮", "😢", "🙏", "🎉", "✅")
MAX_MEMBERS = 30


def request_key(raw):
    try:
        return UUID(str(raw))
    except (ValueError, TypeError, AttributeError):
        raise ValidationError(
            "Mã gửi không hợp lệ. Tải lại trang rồi thử lại."
        ) from None


def touch(room):
    room.revision += 1
    room.updated_at = timezone.now()
    room.save(update_fields=["revision", "last_seq", "updated_at", "title", "owner"])


@transaction.atomic
def create_room(user, ids, title="", group=False):
    ids = sorted(set(int(pk) for pk in ids) | {user.pk})
    if not 2 <= len(ids) <= MAX_MEMBERS:
        raise ValidationError("Chọn từ 1 đến 29 đồng nghiệp để bắt đầu.")
    if not group and len(ids) != 2:
        raise ValidationError("Trò chuyện cá nhân cần đúng hai người.")
    people = access.valid_people(user, ids)
    user = people[user.pk]
    if group:
        access.require_use(user, "chat_groups")
        if not title.strip() or len(title.strip()) > 100:
            raise ValidationError("Tên nhóm từ 1 đến 100 ký tự.")
    direct_key = ":".join(map(str, ids)) if not group else None
    # User-row locks serialize concurrent creation of the same pair.
    existing = (
        Room.objects.filter(direct_key=direct_key).first() if direct_key else None
    )
    if existing:
        return existing
    room = Room.objects.create(
        kind="GROUP" if group else "DIRECT",
        title=title.strip() if group else "",
        direct_key=direct_key,
        owner=user,
    )
    Member.objects.bulk_create([Member(room=room, user_id=pk) for pk in ids])
    return room


@transaction.atomic
def manage_room(user, room_id, command, *, ids=(), title="", owner_id=None):
    room, member = access.membership(user, room_id, locked=True)
    people = access.lock_users(
        set(ids) | {user.pk} | ({int(owner_id)} if owner_id else set())
    )
    user = people[user.pk]
    access.require_use(user)
    if room.kind != "GROUP":
        raise ValidationError("Thao tác này chỉ dành cho nhóm.")
    if command == "leave":
        if room.owner_id == user.pk:
            raise ValidationError("Chuyển trưởng nhóm trước khi rời nhóm.")
        member.active = False
        member.save(update_fields=["active"])
    else:
        access.require_use(user, "chat_groups")
        if room.owner_id != user.pk:
            raise PermissionDenied("Chỉ trưởng nhóm được quản lý thành viên.")
        if command == "rename":
            if not title.strip() or len(title.strip()) > 100:
                raise ValidationError("Tên nhóm từ 1 đến 100 ký tự.")
            room.title = title.strip()
        elif command == "add":
            current = set(
                room.members.filter(active=True).values_list("user_id", flat=True)
            )
            ids = set(int(pk) for pk in ids)
            if not ids or len(current | ids) > MAX_MEMBERS:
                raise ValidationError("Nhóm tối đa 30 thành viên.")
            access.valid_people(user, ids)
            for pk in ids - current:
                Member.objects.update_or_create(
                    room=room,
                    user_id=pk,
                    defaults={
                        "active": True,
                        "joined_seq": room.last_seq,
                        "read_seq": room.last_seq,
                        "joined_at": timezone.now(),
                    },
                )
        elif command in {"remove", "owner"}:
            person = room.members.filter(user_id=owner_id, active=True).first()
            if not person or person.user_id == user.pk:
                raise ValidationError("Chọn một thành viên khác trong nhóm.")
            if command == "remove":
                person.active = False
                person.save(update_fields=["active"])
            else:
                people = access.valid_people(user, [person.user_id])
                if not has_function(people[person.user_id], "chat_groups"):
                    raise ValidationError(
                        "Trưởng nhóm mới cần quyền tạo / quản lý nhóm."
                    )
                room.owner_id = person.user_id
        else:
            raise ValidationError("Thao tác không hợp lệ.")
    # A removed member must also stop participating in an active call.
    from .calls import sync_members

    sync_members(room)
    touch(room)
    return room


def prepare_uploads(uploads):
    if len(uploads) > 3:
        raise ValidationError("Mỗi tin nhắn tối đa 3 ảnh/PDF, tổng không quá 8 MB.")
    if sum(u.size for u in uploads) > 8 * 1024 * 1024:
        raise ValidationError("Tổng tệp trong một tin nhắn tối đa 8 MB.")
    prepared = []
    for upload in uploads:
        suffix = PurePath(upload.name).suffix.lower()
        if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".pdf"}:
            raise ValidationError("Chat chỉ nhận JPG, PNG, WebP và PDF.")
        validated = validate_upload(upload)
        if suffix != ".pdf":
            with Image.open(BytesIO(validated[0])) as image:
                image = ImageOps.exif_transpose(image)
                image.thumbnail((1600, 1600))
                if image.mode in {"RGBA", "LA", "P"}:
                    rgba = image.convert("RGBA")
                    background = Image.new("RGBA", rgba.size, "white")
                    image = Image.alpha_composite(background, rgba)
                output = BytesIO()
                image.convert("RGB").save(
                    output, format="JPEG", quality=82, optimize=True
                )
                if len(output.getvalue()) > 2 * 1024 * 1024:
                    raise ValidationError(
                        "Ảnh quá lớn sau khi xử lý. Hãy giảm kích thước."
                    )
                validated = (output.getvalue(), "image/jpeg")
        filename = (
            "".join(
                c
                for c in upload.name.replace(chr(92), "/").split("/")[-1]
                if 32 <= ord(c) != 127
            )[:140]
            or "tep-dinh-kem"
        )
        if suffix != ".pdf":
            filename = str(PurePath(filename).with_suffix(".jpg"))
        prepared.append((validated, filename))
    return prepared


@transaction.atomic
def send(user, room_id, text, client_key, *, uploads=(), reply_id=None, sticker=""):
    room, member, user = access.lock_member(user, room_id)
    key = request_key(client_key)
    text = text.strip()
    if sticker and sticker not in STICKERS:
        raise ValidationError("Sticker không hợp lệ.")
    if len(text) > 4000 or (not text and not uploads and not sticker):
        raise ValidationError("Nhập tin nhắn (tối đa 4.000 ký tự) hoặc chọn ảnh/PDF.")
    existing = Message.objects.filter(sender=user, client_key=key).first()
    if existing:
        if (
            existing.seq <= member.joined_seq
            or existing.room_id != room.pk
            or existing.text != text
            or existing.sticker != sticker
            or str(existing.reply_to_id or "") != str(reply_id or "")
        ):
            raise ValidationError(
                "Mã gửi đã dùng cho nội dung khác. Không gửi lại mã cũ."
            )
        expected = sorted(existing.attachments.values_list("file__sha256", flat=True))
        if expected != sorted(hashlib.sha256(v[0]).hexdigest() for v, _ in uploads):
            raise ValidationError("Tệp gửi lại khác bản đã gửi trước đó.")
        return existing
    if (
        not access.eligible_users()
        .filter(chat_memberships__room=room, chat_memberships__active=True)
        .exclude(pk=user.pk)
        .exists()
    ):
        raise ValidationError(
            "Chưa có người nhận đang hoạt động được cấp quyền chat trong hội thoại này."
        )
    if (
        Message.objects.filter(
            sender=user, created_at__gte=timezone.now() - timedelta(minutes=1)
        ).count()
        >= 30
    ):
        raise ValidationError("Bạn gửi quá nhanh. Chờ một chút rồi gửi tiếp.")
    reply = None
    if reply_id:
        reply = room.messages.filter(pk=reply_id, seq__gt=member.joined_seq).first()
        if reply is None:
            raise ValidationError(
                "Tin nhắn trả lời không thuộc phần hội thoại bạn được xem."
            )
    room.last_seq += 1
    message = Message.objects.create(
        room=room,
        seq=room.last_seq,
        sender=user,
        text=text,
        sticker=sticker,
        client_key=key,
        reply_to=reply,
    )
    for validated, filename in uploads:
        file = store_file(
            validated,
            {
                "kind": "chat",
                "key": str(room.pk),
                "name": "HoiThoai-" + str(room.pk),
                "year": str(timezone.now().year),
            },
            filename,
        )
        Attachment.objects.create(message=message, file=file, filename=filename)
    touch(room)
    return message


@transaction.atomic
def mark_read(user, room_id, seq):
    room, member, user = access.lock_member(user, room_id)
    if seq < 0 or seq > room.last_seq:
        raise ValidationError("Mốc đã đọc không hợp lệ.")
    if seq > member.read_seq:
        Member.objects.filter(pk=member.pk).update(read_seq=seq)
        Room.objects.filter(pk=room.pk).update(revision=F("revision") + 1)


@transaction.atomic
def react(user, room_id, message_id, emoji):
    room, member, user = access.lock_member(user, room_id)
    if emoji not in EMOJI:
        raise ValidationError("Biểu cảm không được hỗ trợ.")
    message = room.messages.filter(pk=message_id, seq__gt=member.joined_seq).first()
    if message is None:
        raise Http404
    old = Reaction.objects.filter(message=message, user=user).first()
    if old and old.emoji == emoji:
        old.delete()
    else:
        Reaction.objects.update_or_create(
            message=message, user=user, defaults={"emoji": emoji}
        )
    touch(room)
