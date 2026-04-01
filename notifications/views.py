from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from notifications.models import Notification


@login_required
def notification_list(request):
    items = Notification.objects.filter(recipient=request.user)[:50]
    return render(request, "notifications/list.html", {"notifications": items})
