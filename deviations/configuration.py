from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from inventory.access import is_admin

from .forms import CategoryForm, PolicyForm
from .models import Category, PolicyEvent, WorkflowPolicy
from .services.common import active_actors, reason_required
from .services.policies import update_policy


@login_required
def settings(request):
    if not is_admin(request.user):
        raise PermissionDenied
    policy = WorkflowPolicy.objects.filter(pk=1).first() or WorkflowPolicy(pk=1)
    form = PolicyForm(request.POST or None, instance=policy)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data.copy()
            revision, reason = data.pop("revision"), data.pop("reason")
            update_policy(request.user, data, revision, reason)
            messages.success(
                request,
                "Đã lưu phiên bản quy tắc. Hồ sơ đã tiếp nhận giữ quy tắc đã chốt của mình.",
            )
            return redirect("deviation_settings")
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(
        request,
        "deviations/settings.html",
        {
            "form": form,
            "policy": policy,
            "categories": Category.objects.all(),
            "policy_events": PolicyEvent.objects.select_related("actor").order_by(
                "-pk"
            )[:30],
        },
    )


@login_required
def category(request, pk=None):
    if not is_admin(request.user):
        raise PermissionDenied
    category = get_object_or_404(Category, pk=pk) if pk else None
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                user = active_actors(request.user)[request.user.pk]
                if not is_admin(user):
                    raise PermissionDenied
                reason = reason_required(request.POST.get("reason", ""))
                old = Category.objects.select_for_update().get(pk=pk) if pk else None
                if old and old.revision != form.cleaned_data["revision"]:
                    raise ValidationError(
                        "Nhóm vừa được cập nhật. Tải lại trước khi lưu."
                    )
                if old:
                    form.instance.revision = old.revision + 1
                saved = form.save()
                PolicyEvent.objects.create(
                    actor=user,
                    reason=reason,
                    before={
                        "category_id": pk,
                        "name": old.name if old else None,
                        "active": old.active if old else None,
                    },
                    after={
                        "category_id": saved.pk,
                        "name": saved.name,
                        "active": saved.active,
                    },
                )
            return redirect("deviation_settings")
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(
        request,
        "deviations/form.html",
        {"form": form, "form_title": "Nhóm sai lệch", "require_reason": True},
    )
