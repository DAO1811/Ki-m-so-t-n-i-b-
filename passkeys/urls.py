from django.urls import path

from . import unlock_views, views

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
    path("unlock/", unlock_views.unlock, name="app_unlock"),
    path("unlock/options/", unlock_views.unlock_options, name="app_unlock_options"),
    path("unlock/verify/", unlock_views.unlock_verify, name="app_unlock_verify"),
    path("unlock/password/", unlock_views.unlock_password, name="app_unlock_password"),
    path("unlock/ping/", unlock_views.ping, name="app_unlock_ping"),
    path("unlock/lock/", unlock_views.lock_now, name="app_unlock_lock"),
]
