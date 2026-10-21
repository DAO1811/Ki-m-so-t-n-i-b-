from django.urls import path

from . import views

urlpatterns = [
    path("team/", views.team, name="team"),
    path("team/new/", views.employee_form, name="employee_new"),
    path("team/<int:pk>/edit/", views.employee_form, name="employee_edit"),
    path("account/password/", views.password_change, name="password_change"),
]
