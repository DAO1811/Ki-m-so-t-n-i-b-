from django.urls import path

from . import views

urlpatterns = [
    path("camera/verify/", views.verify_page, name="camera_identity_verify_page"),
    path("account/camera/", views.manage, name="camera_identity_manage"),
    path(
        "account/camera/enroll/options/",
        views.enroll_options,
        name="camera_identity_enroll_options",
    ),
    path(
        "account/camera/enroll/verify/",
        views.enroll_verify,
        name="camera_identity_enroll_verify",
    ),
    path("account/camera/remove/", views.remove, name="camera_identity_remove"),
    path(
        "camera/verify/options/",
        views.verify_options,
        name="camera_identity_verify_options",
    ),
    path(
        "camera/verify/finish/",
        views.verify_finish,
        name="camera_identity_verify_finish",
    ),
]
