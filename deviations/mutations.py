"""HTTP forms delegate every business write to transaction services."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from inventory.access import is_admin

from . import access, forms, storage
from .models import Action, Attachment, Extension
from .services import actions, cases, workflow
from .views import case_for


def error_messages(request, form):
    messages.error(
        request,
        " ".join(str(error) for values in form.errors.values() for error in values),
    )


def form_page(request, form, title, case=None):
    return render(
        request,
        "deviations/form.html",
        {"form": form, "form_title": title, "case": case},
    )


@login_required
def case_form(request, pk=None):
    access.require(request.user, "deviations_create")
    case = case_for(request.user, pk) if pk else None
    if case and (
        case.status not in {"DRAFT", "NEEDS_INFO"}
        or (case.created_by_id != request.user.pk and not is_admin(request.user))
    ):
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied(
            "Chỉ sửa bản nháp hoặc phần được yêu cầu bổ sung của mình."
        )
    form = forms.ReportForm(request.POST or None, instance=case, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            saved = (
                cases.edit_case(
                    case.pk,
                    request.user,
                    form.cleaned_data["revision"],
                    form.cleaned_data,
                )
                if case
                else cases.create_case(request.user, form.cleaned_data)
            )
            messages.success(
                request,
                "Đã lưu hồ sơ. Bản nháp chưa được gửi ghi nhận."
                if saved.status == "DRAFT"
                else "Đã lưu phần bổ sung; kiểm tra rồi gửi lại ghi nhận.",
            )
            return redirect("deviation_detail", pk=saved.pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return form_page(
        request, form, "Sửa thông tin sự việc" if case else "Ghi nhận sai lệch", case
    )


@login_required
def analysis(request, pk):
    case = case_for(request.user, pk)
    access.manage(case, request.user)
    form = forms.AnalysisForm(request.POST or None, instance=case)
    if request.method == "POST" and form.is_valid():
        try:
            cases.save_analysis(
                pk, request.user, form.cleaned_data["revision"], form.cleaned_data
            )
            messages.success(request, "Đã lưu xác minh và nguyên nhân.")
            return redirect("deviation_detail", pk=pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return form_page(request, form, "Xác minh & nguyên nhân", case)


@login_required
@require_POST
def assign(request, pk):
    case_for(request.user, pk)
    form = forms.AssignmentForm(request.POST)
    if form.is_valid():
        try:
            cases.assign_case(pk, request.user, **form.cleaned_data)
            messages.success(request, "Đã phân công người phụ trách.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        error_messages(request, form)
    return redirect("deviation_detail", pk=pk)


@login_required
@require_POST
def transition(request, pk):
    case_for(request.user, pk)
    form = forms.TransitionForm(request.POST)
    if form.is_valid():
        try:
            workflow.transition(pk, request.user, **form.cleaned_data)
            messages.success(
                request,
                "Đã cập nhật bước xử lý; không thay đổi tồn kho hoặc hồ sơ ở phân hệ khác.",
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        error_messages(request, form)
    return redirect("deviation_detail", pk=pk)


@login_required
def action_form(request, pk, action_id=None):
    case = case_for(request.user, pk)
    access.manage(case, request.user)
    action = get_object_or_404(Action, pk=action_id, case=case) if action_id else None
    form = forms.ActionForm(request.POST or None, instance=action, case=case)
    if request.method == "POST" and form.is_valid():
        try:
            data = form.cleaned_data.copy()
            revision, action_revision = (
                data.pop("revision"),
                data.pop("action_revision"),
            )
            actions.save_action(
                pk,
                request.user,
                revision,
                data,
                action_id=action_id,
                action_revision=action_revision,
            )
            messages.success(request, "Đã lưu hành động trong kế hoạch.")
            return redirect("deviation_detail", pk=pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return form_page(
        request, form, "Sửa hành động" if action else "Thêm hành động xử lý", case
    )


@login_required
def work(request, pk, action_id):
    case = case_for(request.user, pk)
    action = get_object_or_404(Action, pk=action_id, case=case)
    access.work(action, request.user)
    form = forms.WorkForm(
        request.POST or None,
        initial={
            "revision": case.revision,
            "action_revision": action.revision,
            "status": "IN_PROGRESS",
            "result": action.result,
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            actions.work_action(
                pk, request.user, action_id=action_id, **form.cleaned_data
            )
            messages.success(request, "Đã cập nhật kết quả công việc.")
            return redirect("deviation_detail", pk=pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return form_page(request, form, "Cập nhật thực hiện · " + action.title, case)


@login_required
def extension(request, pk, action_id):
    case = case_for(request.user, pk)
    action = get_object_or_404(Action, pk=action_id, case=case)
    access.work(action, request.user)
    form = forms.ExtensionForm(
        request.POST or None,
        initial={"revision": case.revision, "action_revision": action.revision},
    )
    if request.method == "POST" and form.is_valid():
        try:
            actions.request_extension(
                pk, request.user, action_id=action_id, **form.cleaned_data
            )
            messages.success(
                request, "Đã gửi đề nghị; hạn cũ vẫn giữ đến khi có quyết định."
            )
            return redirect("deviation_detail", pk=pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return form_page(request, form, "Đề nghị gia hạn · " + action.title, case)


@login_required
def extension_decide(request, pk, extension_id):
    case = case_for(request.user, pk)
    extension = get_object_or_404(Extension, pk=extension_id, action__case=case)
    form = forms.DecisionForm(request.POST or None, initial={"revision": case.revision})
    if request.method == "POST" and form.is_valid():
        try:
            actions.decide_extension(
                pk, request.user, extension_id=extension.pk, **form.cleaned_data
            )
            messages.success(request, "Đã lưu quyết định gia hạn và lịch sử.")
            return redirect("deviation_detail", pk=pk)
        except ValidationError as exc:
            form.add_error(None, exc)
    return form_page(request, form, "Xem xét đề nghị gia hạn", case)


@login_required
@require_POST
def evaluate(request, pk):
    case_for(request.user, pk)
    form = forms.EvaluationForm(request.POST)
    if form.is_valid():
        try:
            workflow.evaluate(pk, request.user, **form.cleaned_data)
            messages.success(request, "Đã lưu đánh giá hiệu quả và kết luận.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        error_messages(request, form)
    return redirect("deviation_detail", pk=pk)


@login_required
@require_POST
def upload(request, pk):
    case = case_for(request.user, pk)
    form = forms.UploadForm(request.POST, request.FILES, case=case)
    if form.is_valid():
        try:
            data = form.cleaned_data.copy()
            file = data.pop("file")
            validated = storage.validated_evidence(file)
            storage.add_attachment(
                pk, request.user, validated=validated, filename=file.name, **data
            )
            messages.success(request, "Đã lưu bằng chứng và thông tin đối chiếu.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        error_messages(request, form)
    return redirect("deviation_detail", pk=pk)


@login_required
@require_POST
def void_file(request, pk, attachment_id):
    case_for(request.user, pk)
    get_object_or_404(Attachment, pk=attachment_id, case_id=pk)
    form = forms.VoidForm(request.POST)
    if form.is_valid():
        try:
            storage.void_attachment(
                pk, request.user, attachment_id=attachment_id, **form.cleaned_data
            )
            messages.success(
                request, "Đã đánh dấu tệp không sử dụng; bản gốc vẫn giữ trong lịch sử."
            )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
    else:
        error_messages(request, form)
    return redirect("deviation_detail", pk=pk)
