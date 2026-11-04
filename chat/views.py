import json
from functools import wraps
from hashlib import sha256
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from inventory.access import has_function
from inventory.models import StoredFile

from . import access, calls, directory, selectors, services
from .models import Attachment, Call, Member
from .stickers import STICKERS


def api(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                {"error": "Phiên đăng nhập đã hết. Đăng nhập lại để tiếp tục."},
                status=401,
            )
        try:
            access.require_use(request.user)
            response = view(request, *args, **kwargs)
        except PermissionDenied:
            response = JsonResponse(
                {"error": "Bạn không có quyền thực hiện thao tác này."}, status=403
            )
        except Http404:
            response = JsonResponse(
                {"error": "Không tìm thấy hội thoại hoặc nội dung được phép xem."},
                status=404,
            )
        except (ValueError, TypeError, ValidationError) as exc:
            response = JsonResponse(
                {
                    "error": " ".join(exc.messages)
                    if isinstance(exc, ValidationError)
                    else "Thông tin gửi lên không hợp lệ."
                },
                status=400,
            )
        response["Cache-Control"] = "private, no-store"
        response["Vary"] = "Cookie"
        return response

    return wrapped


def body(request):
    if len(request.body) > 75000:
        raise ValidationError("Yêu cầu quá lớn.")
    try:
        data = json.loads(request.body or "{}")
    except (ValueError, UnicodeDecodeError):
        raise ValidationError("Dữ liệu không hợp lệ.") from None
    if not isinstance(data, dict):
        raise ValidationError("Dữ liệu không hợp lệ.")
    return data


def bounded_int(value, maximum=2**53 - 1):
    if isinstance(value, bool):
        raise ValueError
    n = int(value)
    if n < 0 or n > maximum:
        raise ValueError
    return n


@login_required
@ensure_csrf_cookie
@require_GET
def home(request, room_id=None):
    access.require_use(request.user)
    room = None
    if room_id:
        room, _ = access.membership(request.user, room_id)
    response = render(
        request,
        "chat/home.html",
        {
            "chat_bootstrap": {
                "user_id": request.user.pk,
                "room_id": str(room.pk) if room else "",
                "can_groups": has_function(request.user, "chat_groups"),
                "can_call": has_function(request.user, "chat_call"),
                "emojis": list(services.EMOJI),
                "stickers": list(STICKERS.values()),
                "relay_configured": bool(
                    calls.settings.CHAT_TURN_URLS and calls.settings.CHAT_TURN_SECRET
                ),
            }
        },
    )
    response["Cache-Control"] = "private, no-store"
    return response


@api
@require_GET
def summary(request):
    compact = request.GET.get("compact") == "1"
    rooms = (
        selectors.inbox(request.user, request.GET.get("q", "")[:100], compact=compact)
        if request.GET.get("rooms") != "0"
        else []
    )
    return JsonResponse(
        {
            "rooms": rooms,
            "unread": selectors.unread_total(request.user),
            "incoming": selectors.incoming(request.user)
            if has_function(request.user, "chat_call")
            else [],
        }
    )


@api
@require_GET
def people(request):
    return JsonResponse(directory.directory(request.user, request.GET))


@api
@require_GET
def groups(request):
    return JsonResponse(directory.groups(request.user, request.GET))


@api
@require_POST
def create(request):
    data = body(request)
    ids = data.get("members", [])
    if not isinstance(ids, list) or len(ids) > services.MAX_MEMBERS:
        raise ValueError
    room = services.create_room(
        request.user, ids, str(data.get("title", "")), data.get("group") is True
    )
    return JsonResponse(
        {"id": str(room.pk), "url": reverse("chat_room", args=[room.pk])}
    )


@api
@require_POST
def manage(request, room_id):
    data = body(request)
    ids = data.get("members", [])
    if not isinstance(ids, list) or len(ids) > services.MAX_MEMBERS:
        raise ValueError
    services.manage_room(
        request.user,
        room_id,
        data.get("command"),
        ids=ids,
        title=str(data.get("title", "")),
        owner_id=data.get("user_id"),
    )
    return JsonResponse({"ok": True})


@api
@require_GET
def timeline(request, room_id):
    room, member, messages = access.visible_messages(request.user, room_id)
    room.members_cache = list(room.members.select_related("user"))
    if (
        request.GET.get("version")
        and bounded_int(request.GET["version"]) == room.revision
        and not request.GET.get("q")
        and not request.GET.get("before")
    ):
        return JsonResponse(
            {
                "unchanged": True,
                "typing": [
                    access.name(m.user)
                    for m in room.members_cache
                    if m.active
                    and m.user_id != request.user.pk
                    and m.typing_until
                    and m.typing_until > timezone.now()
                ],
                "call": selectors.current_call(room, request.user, member)
                if has_function(request.user, "chat_call")
                else None,
            }
        )
    before = bounded_int(request.GET.get("before", 0))
    after = bounded_int(request.GET.get("after", 0))
    q = request.GET.get("q", "").strip()[:100]
    if before and after:
        raise ValueError
    if q:
        messages = messages.filter(text__icontains=q)
    if before:
        messages = messages.filter(seq__lt=before)
    if after:
        selected = list(
            selectors.message_query(messages.filter(seq__gt=after)).order_by("seq")[:51]
        )
        more = len(selected) > 50
        selected = selected[:50]
    else:
        selected = list(selectors.message_query(messages).order_by("-seq")[:51])
        more = len(selected) > 50
        selected = list(reversed(selected[:50]))
    # Last-page refresh carries reactions/read receipts without downloading history.
    updates = (
        list(selectors.message_query(messages).order_by("-seq")[:50])
        if after and not q
        else []
    )

    def render_message(message):
        return selectors.message_data(message, request.user, member, room.members_cache)

    return JsonResponse(
        {
            "room": selectors.room_data(room, request.user, member),
            "messages": [render_message(m) for m in selected],
            "updates": [render_message(m) for m in reversed(updates)],
            "more": more,
            "typing": [
                access.name(m.user)
                for m in room.members_cache
                if m.active
                and m.user_id != request.user.pk
                and m.typing_until
                and m.typing_until > timezone.now()
            ],
            "call": selectors.current_call(room, request.user, member)
            if has_function(request.user, "chat_call")
            else None,
        }
    )


@api
@require_POST
def send(request, room_id):
    # Authenticate room before parsing/validating any uploaded file.
    access.membership(request.user, room_id)
    prepared = services.prepare_uploads(request.FILES.getlist("files"))
    message = services.send(
        request.user,
        room_id,
        request.POST.get("text", ""),
        request.POST.get("client_key"),
        uploads=prepared,
        reply_id=request.POST.get("reply_id") or None,
        sticker=request.POST.get("sticker", ""),
    )
    return JsonResponse({"id": str(message.pk), "seq": message.seq})


@api
@require_POST
def read(request, room_id):
    services.mark_read(request.user, room_id, bounded_int(body(request).get("seq")))
    return JsonResponse({"ok": True})


@api
@require_POST
def reaction(request, room_id, message_id):
    services.react(request.user, room_id, message_id, body(request).get("emoji"))
    room, member, messages = access.visible_messages(request.user, room_id)
    message = selectors.message_query(messages).get(pk=message_id)
    return JsonResponse(
        {
            "message": selectors.message_data(
                message, request.user, member, list(room.members.select_related("user"))
            )
        }
    )


@api
@require_POST
def typing(request, room_id):
    from datetime import timedelta

    from django.db import transaction

    with transaction.atomic():
        room, member, user = access.lock_member(request.user, room_id)
        Member.objects.filter(pk=member.pk).update(
            typing_until=timezone.now() + timedelta(seconds=6)
        )
    return JsonResponse({"ok": True})


@login_required
@require_GET
def file(request, file_id):
    access.require_use(request.user)
    attachment = get_object_or_404(
        Attachment.objects.select_related("message__room"), pk=file_id
    )
    room, member = access.membership(request.user, attachment.message.room_id)
    if attachment.message.seq <= member.joined_seq:
        raise Http404
    stored = StoredFile.objects.defer("data").get(pk=attachment.file_id)
    try:
        if stored.provider == "drive":
            from inventory.drive import download

            content = download(stored)
        else:
            content = bytes(
                type(stored).objects.only("data").get(pk=stored.pk).data or b""
            )
        if len(content) != stored.size or sha256(content).hexdigest() != stored.sha256:
            raise ValidationError("Tệp không còn khớp bản đã gửi.")
    except ValidationError:
        return HttpResponse(
            "Chưa tải được tệp. Hãy thử lại hoặc nhờ quản trị viên kiểm tra kết nối lưu trữ.",
            status=503,
            content_type="text/plain; charset=utf-8",
        )
    response = FileResponse(
        BytesIO(content),
        content_type=stored.content_type,
        filename=attachment.filename,
        as_attachment=not stored.content_type.startswith("image/"),
    )
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Cookie"
    response["X-Content-Type-Options"] = "nosniff"
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response


@api
@require_GET
def files(request, room_id):
    room, member, messages = access.visible_messages(request.user, room_id)
    qs = (
        Attachment.objects.filter(message__in=messages)
        .select_related("file")
        .defer("file__data")
        .order_by("-message__seq")
    )
    cursor = request.GET.get("before", "")
    if cursor:
        from django.db.models import Q

        anchor = get_object_or_404(qs, pk=cursor)
        qs = qs.filter(
            Q(message__seq__lt=anchor.message.seq)
            | Q(message__seq=anchor.message.seq, id__lt=anchor.pk)
        )
    q = request.GET.get("q", "").strip()[:100]
    if q:
        qs = qs.filter(filename__icontains=q)
    chosen = list(qs.order_by("-message__seq", "-pk")[:31])
    return JsonResponse(
        {
            "files": [
                {
                    "id": str(a.pk),
                    "name": a.filename,
                    "image": a.file.content_type.startswith("image/"),
                    "url": reverse("chat_file", args=[a.pk]),
                    "seq": a.message.seq,
                }
                for a in chosen[:30]
            ],
            "next": str(chosen[29].pk) if len(chosen) > 30 else None,
        }
    )


@api
@require_POST
def call_start(request, room_id):
    data = body(request)
    call = calls.start(
        request.user,
        room_id,
        data.get("mode"),
        data.get("client_key"),
        data.get("device_key"),
    )
    return JsonResponse(
        {
            "call": selectors.call_data(call, request.user),
            "ice_servers": calls.ice_servers(request.user),
        }
    )


@api
@require_POST
def call_action(request, room_id, call_id):
    call = calls.act(
        request.user,
        room_id,
        call_id,
        body(request).get("command"),
        body(request).get("device_key"),
    )
    return JsonResponse(
        {
            "call": selectors.call_data(call, request.user),
            "ice_servers": calls.ice_servers(request.user),
        }
    )


@api
@require_POST
def call_signal(request, room_id, call_id):
    data = body(request)
    signal = calls.signal(
        request.user,
        room_id,
        call_id,
        bounded_int(data.get("target")),
        data.get("kind"),
        data.get("payload"),
        data.get("client_key"),
        data.get("device_key"),
    )
    return JsonResponse({"id": signal.pk})


@api
@require_GET
def call_events(request, room_id, call_id):
    call, signals = calls.signals(
        request.user,
        room_id,
        call_id,
        bounded_int(request.GET.get("after", 0)),
        request.GET.get("device_key"),
    )
    return JsonResponse(
        {
            "call": selectors.call_data(call, request.user),
            "signals": [
                {
                    "id": s.pk,
                    "sender": s.sender_id,
                    "kind": s.kind,
                    "payload": s.payload,
                }
                for s in signals
            ],
        }
    )


@api
@require_GET
def call_history(request, room_id):
    room, member = access.membership(request.user, room_id)
    qs = (
        Call.objects.filter(room=room, created_at__gte=member.joined_at)
        .select_related("initiator")
        .order_by("-created_at")[:30]
    )
    return JsonResponse({"calls": [selectors.call_data(c, request.user) for c in qs]})
