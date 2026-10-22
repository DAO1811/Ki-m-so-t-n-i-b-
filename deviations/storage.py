"""Adapter to existing private storage; no credentials or Drive SDK in business rules."""

from hashlib import sha256
from pathlib import PurePath

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from inventory.access import has_function, is_admin
from inventory.media import store_file, validate_upload
from inventory.models import StoredFile

from . import access
from .constants import CaseStatus
from .models import Attachment
from .services.common import (
    active_actors,
    locked_case,
    reason_required,
    record,
    snapshot,
)


def can_upload(case, user):
    if case.is_terminal:
        return False
    return bool(
        is_admin(user)
        or (
            case.created_by_id == user.pk
            and has_function(user, "deviations_create")
            and case.status
            in {CaseStatus.DRAFT, CaseStatus.REPORTED, CaseStatus.NEEDS_INFO}
        )
        or (case.owner_id == user.pk and has_function(user, "deviations_manage"))
        or (
            has_function(user, "deviations_work")
            and case.actions.filter(assignee=user, round=case.round).exists()
        )
    )


def validated_evidence(upload):
    if PurePath(upload.name).suffix.lower() not in {
        ".jpg",
        ".jpeg",
        ".png",
        ".webp",
        ".pdf",
    }:
        raise ValidationError(
            "Hồ sơ sai lệch nhận JPG, PNG, WebP hoặc PDF, tối đa 8 MB."
        )
    return validate_upload(upload)


@transaction.atomic
def add_attachment(pk, user, revision, validated, filename, description, action=None):
    case = locked_case(pk, revision)
    user = active_actors(user)[user.pk]
    access.require_member(user)
    if not can_upload(case, user):
        raise PermissionDenied(
            "Chưa có quyền bổ sung bằng chứng hoặc hồ sơ đã kết thúc."
        )
    if action and (action.case_id != case.pk or action.round != case.round):
        raise ValidationError("Công việc đính kèm không thuộc lượt xử lý này.")
    if not description.strip() or len(description) > 250:
        raise ValidationError("Ghi nội dung/căn cứ của tệp, tối đa 250 ký tự.")
    existing = case.attachments.filter(
        file__sha256=sha256(validated[0]).hexdigest(), voided_at__isnull=True
    ).first()
    if existing:
        return existing
    if case.attachments.count() >= 50:
        raise ValidationError("Mỗi hồ sơ tối đa 50 tệp, tính cả tệp giữ lịch sử.")
    filename = (
        "".join(
            c
            for c in str(filename).replace(chr(92), "/").split("/")[-1]
            if ord(c) >= 32 and ord(c) != 127
        )[:150]
        or "bang-chung"
    )
    file = store_file(
        validated,
        {
            "kind": "deviation",
            "key": str(case.token),
            "name": case.code,
            "year": str(case.created_at.year),
        },
        filename,
    )
    before = snapshot(case)
    attachment = Attachment.objects.create(
        case=case,
        action=action,
        file=file,
        stage=case.status,
        round=case.round,
        filename=filename,
        description=description,
        uploaded_by=user,
    )
    record(
        case,
        user,
        "Bổ sung bằng chứng",
        before,
        extra={
            "attachment_id": attachment.pk,
            "sha256": file.sha256,
            "filename": filename,
            "description": description,
            "stage": case.status,
            "round": case.round,
        },
    )
    return attachment


@transaction.atomic
def void_attachment(pk, user, revision, attachment_id, reason):
    case = locked_case(pk, revision)
    user = active_actors(user)[user.pk]
    if not is_admin(user):
        raise PermissionDenied
    if case.is_terminal:
        raise ValidationError(
            "Mở lại hồ sơ đúng quy trình trước khi thay đổi việc sử dụng bằng chứng."
        )
    attachment = Attachment.objects.select_for_update().get(pk=attachment_id, case=case)
    if attachment.voided_at:
        raise ValidationError("Tệp đã được đánh dấu trước đó.")
    before = snapshot(case)
    attachment.void_reason = reason_required(reason)
    attachment.voided_by, attachment.voided_at = user, timezone.now()
    attachment.save()
    record(
        case,
        user,
        "Đánh dấu tệp không sử dụng",
        before,
        attachment.void_reason,
        {"attachment_id": attachment.pk},
    )
    return attachment


def content(file_id):
    file = StoredFile.objects.get(pk=file_id)
    if file.provider == "drive":
        from inventory.drive import download

        return file, download(file)
    data = bytes(file.data or b"")
    if len(data) != file.size or sha256(data).hexdigest() != file.sha256:
        raise ValidationError("Tệp không còn khớp bản gốc. Cần đối chiếu bằng chứng.")
    return file, data
