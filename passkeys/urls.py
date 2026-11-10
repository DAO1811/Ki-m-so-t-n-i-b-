from django.urls import path

from . import views

urlpatterns = [
    path("account/passkeys/", views.manage, name="passkeys_manage"),
    path(
        "account/passkeys/register/options/",
        views.register_options,
        name="passkeys_register_options",
    ),
    path(
        "account/passkeys/register/verify/",
        views.register_verify,
        name="passkeys_register_verify",
    ),
    path("account/passkeys/<int:pk>/remove/", views.remove, name="passkeys_remove"),
    path("passkeys/login/options/", views.login_options, name="passkeys_login_options"),
    path("passkeys/login/verify/", views.login_verify, name="passkeys_login_verify"),
]
