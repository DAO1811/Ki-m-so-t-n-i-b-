from django.contrib.admin.apps import AdminConfig


class CompanyAdminConfig(AdminConfig):
    default_site = "config.admin_site.CompanyAdminSite"
