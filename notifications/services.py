from django.contrib.auth import get_user_model

from notifications.models import Notification

User = get_user_model()


def notify_user(user, *, title: str, body: str = "", related_case_id: int | None = None):
    if not user or not user.is_authenticated:
        return None
    return Notification.objects.create(
        recipient=user,
        title=title,
        body=body,
        related_case_id=related_case_id,
    )
