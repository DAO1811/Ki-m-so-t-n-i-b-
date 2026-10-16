from django.contrib import admin
from django.contrib.auth import views as auth
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", auth.LoginView.as_view(template_name="login.html"), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path("", include("inventory.urls")),
]
admin.site.site_header = "Kho Việt · Quản trị hệ thống"
admin.site.site_title = "Kho Việt"
admin.site.index_title = "Danh mục, nhân viên và phân quyền"
