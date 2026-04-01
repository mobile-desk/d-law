from django.contrib import admin

from notifications.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("recipient", "title", "read", "created_at")
    list_filter = ("read",)
    raw_id_fields = ("recipient",)
