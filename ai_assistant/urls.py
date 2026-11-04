from django.urls import path

from . import cloud_views
from .views import answer_context

urlpatterns = [
    path("api/context/", answer_context, name="assistant_context"),
    path("api/cloud/status/", cloud_views.cloud_status, name="assistant_cloud_status"),
    path("api/cloud/start/", cloud_views.cloud_start, name="assistant_cloud_start"),
    path(
        "api/cloud/jobs/<uuid:pk>/",
        cloud_views.cloud_result,
        name="assistant_cloud_result",
    ),
    path(
        "api/cloud/jobs/<uuid:pk>/cancel/",
        cloud_views.cloud_cancel,
        name="assistant_cloud_cancel",
    ),
]
