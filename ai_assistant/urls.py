from django.urls import path

from .views import answer_context

urlpatterns = [path("api/context/", answer_context, name="assistant_context")]
