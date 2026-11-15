from django.urls import path

from . import views

urlpatterns = [
    path("account/devices/", views.my_sessions, name="device_sessions"),
    path(
        "account/devices/<int:pk>/logout/",
        views.logout_device,
        name="device_session_logout",
    ),
    path(
        "account/devices/logout-others/",
        views.logout_others,
        name="device_sessions_logout_others",
    ),
    path(
        "team/<int:pk>/logout-everywhere/",
        views.admin_logout_user,
        name="employee_logout_everywhere",
    ),
]
