from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.views.decorators.http import require_safe


@login_required
@require_safe
def module_placeholder(request, module):
    labels = {"processes": "Quy trình", "human_resources": "Quản lý nhân sự"}
    if module not in labels:
        raise Http404
    return render(request, "module_placeholder.html", {"module_title": labels[module]})
