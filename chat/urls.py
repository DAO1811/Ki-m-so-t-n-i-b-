from django.urls import path

from . import views

urlpatterns = [
    path("", views.home, name="chat_home"),
    path("rooms/<uuid:room_id>/", views.home, name="chat_room"),
    path("api/summary/", views.summary, name="chat_summary"),
    path("api/people/", views.people, name="chat_people"),
    path("api/groups/", views.groups, name="chat_groups"),
    path("api/rooms/", views.create, name="chat_create"),
    path("api/rooms/<uuid:room_id>/manage/", views.manage, name="chat_manage"),
    path("api/rooms/<uuid:room_id>/messages/", views.timeline, name="chat_messages"),
    path("api/rooms/<uuid:room_id>/send/", views.send, name="chat_send"),
    path("api/rooms/<uuid:room_id>/read/", views.read, name="chat_read"),
    path("api/rooms/<uuid:room_id>/typing/", views.typing, name="chat_typing"),
    path(
        "api/rooms/<uuid:room_id>/messages/<uuid:message_id>/reaction/",
        views.reaction,
        name="chat_react",
    ),
    path("api/rooms/<uuid:room_id>/files/", views.files, name="chat_files"),
    path("files/<uuid:file_id>/", views.file, name="chat_file"),
    path("api/rooms/<uuid:room_id>/calls/", views.call_start, name="chat_call_start"),
    path(
        "api/rooms/<uuid:room_id>/calls/history/",
        views.call_history,
        name="chat_call_history",
    ),
    path(
        "api/rooms/<uuid:room_id>/calls/<uuid:call_id>/action/",
        views.call_action,
        name="chat_call_action",
    ),
    path(
        "api/rooms/<uuid:room_id>/calls/<uuid:call_id>/signal/",
        views.call_signal,
        name="chat_call_signal",
    ),
    path(
        "api/rooms/<uuid:room_id>/calls/<uuid:call_id>/events/",
        views.call_events,
        name="chat_call_events",
    ),
]
