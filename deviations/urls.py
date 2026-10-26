from django.urls import path

from . import configuration, mutations, views

urlpatterns = [
    path(
        "cases/<int:pk>/approvals/<int:run_id>/print/",
        views.approval_print,
        name="deviation_approval_print",
    ),
    path(
        "cases/<int:pk>/approvals/<int:run_id>/decide/",
        mutations.approval_decide,
        name="deviation_approval_decide",
    ),
    path(
        "cases/<int:pk>/approvals/<int:run_id>/recall/",
        mutations.approval_recall,
        name="deviation_approval_recall",
    ),
    path("", views.overview, name="deviations"),
    path("cases/", views.case_list, name="deviation_list"),
    path("cases/new/", mutations.case_form, name="deviation_new"),
    path("cases/<int:pk>/", views.case_detail, name="deviation_detail"),
    path("cases/<int:pk>/edit/", mutations.case_form, name="deviation_edit"),
    path("cases/<int:pk>/analysis/", mutations.analysis, name="deviation_analysis"),
    path("cases/<int:pk>/assign/", mutations.assign, name="deviation_assign"),
    path(
        "cases/<int:pk>/transition/", mutations.transition, name="deviation_transition"
    ),
    path(
        "cases/<int:pk>/actions/new/",
        mutations.action_form,
        name="deviation_action_new",
    ),
    path(
        "cases/<int:pk>/actions/<int:action_id>/edit/",
        mutations.action_form,
        name="deviation_action_edit",
    ),
    path(
        "cases/<int:pk>/actions/<int:action_id>/work/",
        mutations.work,
        name="deviation_action_work",
    ),
    path(
        "cases/<int:pk>/actions/<int:action_id>/extend/",
        mutations.extension,
        name="deviation_extension",
    ),
    path(
        "cases/<int:pk>/extensions/<int:extension_id>/",
        mutations.extension_decide,
        name="deviation_extension_decide",
    ),
    path("cases/<int:pk>/evaluate/", mutations.evaluate, name="deviation_evaluate"),
    path("cases/<int:pk>/files/", mutations.upload, name="deviation_upload"),
    path(
        "cases/<int:pk>/files/<int:attachment_id>/void/",
        mutations.void_file,
        name="deviation_void_file",
    ),
    path("cases/<int:pk>/print/", views.print_case, name="deviation_print"),
    path("files/<int:pk>/", views.evidence_file, name="deviation_file"),
    path("reports/", views.reports, name="deviation_reports"),
    path("settings/", configuration.settings, name="deviation_settings"),
    path("settings/categories/new/", configuration.category, name="deviation_category"),
    path(
        "settings/categories/<int:pk>/",
        configuration.category,
        name="deviation_category_edit",
    ),
]
