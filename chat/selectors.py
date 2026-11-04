from datetime import timedelta

from django.db.models import Count, OuterRef, Prefetch, Subquery, Sum
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from . import access
from .models import Attachment, Call, Member, Message, Room
from .stickers import STICKERS


def room_title(room, user):
    if room.kind == "GROUP":
        return room.title
    return next(
        (access.name(m.user) for m in room.members.all() if m.user_id != user.pk),
        "Cuộc trò chuyện",
    )


def room_data(room, user, membership=None):
    members = [m for m in room.members.all() if m.active]
    mine = membership or next(m for m in members if m.user_id == user.pk)
    return {
        "id": str(room.pk),
        "title": room_title(room, user),
        "kind": room.kind,
        "owner_id": room.owner_id,
        "last_seq": room.last_seq,
        "revision": room.revision,
        "unread": getattr(mine, "unread_count", None)
        if hasattr(mine, "unread_count")
        else room.messages.filter(seq__gt=mine.read_seq).exclude(sender=user).count(),
        "url": reverse("chat_room", args=[room.pk]),
        "members": [
            {
                "id": m.user_id,
                "name": access.name(m.user),
                "username": m.user.username,
                "active": m.user.is_active,
                "read_seq": m.read_seq,
                "joined_seq": m.joined_seq,
            }
            for m in members
        ],
    }


def memberships_with_unread(user):
    unread = (
        Message.objects.filter(
            room_id=OuterRef("room_id"), seq__gt=OuterRef("read_seq")
        )
        .exclude(sender=user)
        .order_by()
        .values("room_id")
        .annotate(n=Count("pk"))
        .values("n")
    )
    return Member.objects.filter(user=user, active=True).annotate(
        unread_count=Coalesce(Subquery(unread[:1]), 0)
    )


def unread_total(user):
    return memberships_with_unread(user).aggregate(n=Sum("unread_count"))["n"] or 0


def inbox(user, query="", compact=False):
    access.require_use(user)
    qs = (
        memberships_with_unread(user)
        .select_related("room")
        .order_by("-room__updated_at")
    )
    if query:
        from django.db.models import Q

        qs = qs.filter(
            Q(room__title__icontains=query)
            | Q(room__members__user__username__icontains=query)
            | Q(room__members__user__first_name__icontains=query)
            | Q(room__members__user__last_name__icontains=query)
        ).distinct()
    members = list(qs[:50])
    if compact:
        direct_ids = [m.room_id for m in members if m.room.kind == "DIRECT"]
        others = {
            m.room_id: access.name(m.user)
            for m in Member.objects.filter(room_id__in=direct_ids)
            .exclude(user=user)
            .select_related("user")
        }
        return [
            {
                "id": str(m.room_id),
                "title": m.room.title
                if m.room.kind == "GROUP"
                else others.get(m.room_id, "Cuộc trò chuyện"),
                "kind": m.room.kind,
                "url": reverse("chat_room", args=[m.room_id]),
                "unread": m.unread_count,
                "member_count": 2 if m.room.kind == "DIRECT" else None,
            }
            for m in members
        ]
    room_ids = [m.room_id for m in members]
    rooms = (
        {
            r.pk: r
            for r in Room.objects.filter(pk__in=room_ids).prefetch_related(
                Prefetch("members", queryset=Member.objects.select_related("user"))
            )
        }
        if members
        else {}
    )
    return [room_data(rooms[m.room_id], user, m) for m in members]


def message_query(qs):
    return qs.select_related("sender", "reply_to__sender").prefetch_related(
        Prefetch(
            "attachments",
            queryset=Attachment.objects.select_related("file").defer("file__data"),
        ),
        "reactions",
    )


def message_data(message, user, mine, members):
    quote = message.reply_to
    reply = None
    if quote:
        reply = (
            {
                "id": str(quote.pk),
                "name": access.name(quote.sender),
                "text": (quote.text or "Sticker / tệp")[:160],
            }
            if quote.seq > mine.joined_seq
            else {
                "id": "",
                "name": "Tin nhắn trước khi bạn tham gia",
                "text": "Nội dung không được chia sẻ",
            }
        )
    counts = {}
    for reaction in message.reactions.all():
        entry = counts.setdefault(
            reaction.emoji, {"emoji": reaction.emoji, "count": 0, "mine": False}
        )
        entry["count"] += 1
        entry["mine"] |= reaction.user_id == user.pk
    return {
        "id": str(message.pk),
        "seq": message.seq,
        "text": message.text,
        "sticker": STICKERS.get(message.sticker),
        "sender": {"id": message.sender_id, "name": access.name(message.sender)},
        "mine": message.sender_id == user.pk,
        "at": message.created_at.isoformat(),
        "reply": reply,
        "reactions": list(counts.values()),
        "read_by": [
            access.name(m.user)
            for m in members
            if m.active
            and m.user_id != message.sender_id
            and m.joined_seq < message.seq <= m.read_seq
        ],
        "files": [
            {
                "id": str(a.pk),
                "name": a.filename,
                "size": a.file.size,
                "image": a.file.content_type.startswith("image/"),
                "url": reverse("chat_file", args=[a.pk]),
            }
            for a in message.attachments.all()
        ],
    }


def call_data(call, user):
    return {
        "id": str(call.pk),
        "room_id": str(call.room_id),
        "mode": call.mode,
        "status": call.status,
        "reason": call.end_reason,
        "initiator_id": call.initiator_id,
        "initiator_name": access.name(call.initiator),
        "at": call.created_at.isoformat(),
        "ended_at": call.ended_at.isoformat() if call.ended_at else None,
        "participants": [
            {"id": p.user_id, "name": access.name(p.user), "state": p.state}
            for p in call.participants.select_related("user").all()
        ],
        "url": reverse("chat_room", args=[call.room_id]) + "?call=" + str(call.pk),
    }


def current_call(room, user, membership):
    call = (
        room.calls.filter(
            status__in=["RINGING", "ACTIVE"],
            touched_at__gte=timezone.now() - timedelta(seconds=100),
            created_at__gte=membership.joined_at,
        )
        .select_related("initiator")
        .first()
    )
    return call_data(call, user) if call else None


def incoming(user):
    access.require_use(user)
    calls = (
        Call.objects.filter(
            participants__user=user,
            participants__state="INVITED",
            status__in=["RINGING", "ACTIVE"],
            room__members__user=user,
            room__members__active=True,
            touched_at__gte=timezone.now() - timedelta(seconds=90),
        )
        .exclude(initiator=user)
        .select_related("initiator")
        .order_by("-created_at")[:5]
    )
    return [call_data(c, user) for c in calls]
