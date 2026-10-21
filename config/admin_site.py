from django.contrib.admin import AdminSite

from inventory.access import is_admin


class CompanyAdminSite(AdminSite):
    def has_permission(self, request):
        return is_admin(request.user)
