from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import include, path

from .health import health

urlpatterns = [
    path("healthz/", health, name="health"),
    path("admin/", admin.site.urls),
    path("login/", auth.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path("", include("core.urls")),
    path("processes/", include("workflows.urls")),
    path("human-resources/", include("people.urls")),
    path("", include("inventory.urls")),
]
admin.site.site_header = "Kho Việt · Quản trị hệ thống"
admin.site.site_title = "Kho Việt"
admin.site.index_title = "Danh mục, nhân viên và phân quyền"
