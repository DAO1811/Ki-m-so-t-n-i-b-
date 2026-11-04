from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models import Q
from django.http import Http404

from inventory.access import has_function
from inventory.models import FunctionAccess

from .models import Member, Room


def name(user):
    return user.get_full_name().strip() or user.username


def require_use(user, permission="chat_use"):
    if not has_function(user, permission):
        raise PermissionDenied(
            "Bạn chưa được cấp quyền dùng nhắn tin / cuộc gọi nội bộ."
        )


def eligible_users():
    users = get_user_model().objects.filter(is_active=True)
    if connection.vendor == "postgresql":
        permitted = Q(function_access__permissions__contains=["chat_use"])
    else:
        ids = [
            row.user_id
            for row in FunctionAccess.objects.only("user_id", "permissions")
            if "chat_use" in row.permissions
        ]
        permitted = Q(pk__in=ids)
    return users.filter(Q(is_superuser=True) | permitted).order_by(
        "first_name", "username"
    )


def lock_users(ids):
    users = {
        u.pk: u
        for u in get_user_model()
        .objects.select_for_update()
        .filter(pk__in=ids)
        .order_by("pk")
    }
    list(
        FunctionAccess.objects.select_for_update()
        .filter(user_id__in=ids)
        .order_by("user_id")
    )
    return users


def membership(user, room_id, *, locked=False):
    require_use(user)
    rooms = Room.objects.select_for_update() if locked else Room.objects
    room = rooms.filter(pk=room_id).first()
    member = Member.objects.filter(room_id=room_id, user=user, active=True).first()
    # Deliberately no superuser shortcut. Missing and private rooms look the same.
    if room is None or member is None:
        raise Http404("Không tìm thấy cuộc trò chuyện.")
    return room, member


def visible_messages(user, room_id):
    room, member = membership(user, room_id)
    return room, member, room.messages.filter(seq__gt=member.joined_seq)


def valid_people(actor, ids):
    people = lock_users(set(ids) | {actor.pk})
    require_use(people[actor.pk])
    if set(people) != set(ids) | {actor.pk}:
        raise ValidationError("Có tài khoản không còn tồn tại.")
    for person in people.values():
        require_use(person)
    return people


def lock_member(user, room_id):
    # All chat writers use room -> sorted user/grant locks, including membership changes.
    room, member = membership(user, room_id, locked=True)
    people = lock_users([user.pk])
    require_use(people[user.pk])
    return room, member, people[user.pk]
