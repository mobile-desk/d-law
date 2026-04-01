from django.urls import path

from notifications.views import notification_list

app_name = "notifications"

urlpatterns = [
    path("", notification_list, name="list"),
]
