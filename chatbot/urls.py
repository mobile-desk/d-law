from django.urls import path

from chatbot.views import chat_view, intake_start

app_name = "chatbot"

urlpatterns = [
    path("", intake_start, name="start"),
    path("<int:case_id>/", chat_view, name="chat"),
]
