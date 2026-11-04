import json

from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from .context import context_for


@require_POST
def answer_context(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Đăng nhập lại để dùng Trợ lý AI."}, status=401)
    try:
        if len(request.body) > 8000:
            raise ValueError
        data = json.loads(request.body)
        question = data.get("question")
        if not isinstance(question, str) or not 1 <= len(question.strip()) <= 1000:
            raise ValueError
        result = context_for(
            request.user,
            question.strip(),
            data.get("page", "/"),
            data.get("warehouse", ""),
        )
        response = JsonResponse(result)
    except PermissionDenied as e:
        response = JsonResponse({"error": str(e)}, status=403)
    except (ValueError, TypeError, AttributeError):
        response = JsonResponse(
            {"error": "Câu hỏi hoặc ngữ cảnh không hợp lệ; tối đa 1.000 ký tự."},
            status=400,
        )
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Cookie"
    return response
