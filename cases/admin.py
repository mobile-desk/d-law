from django.contrib import admin

from cases.models import Case, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("created_at",)


@admin.register(Case)
class CaseAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "category", "user", "assigned_to", "is_anonymous", "created_at")
    list_filter = ("status", "is_anonymous")
    search_fields = ("description", "category")
    raw_id_fields = ("user", "assigned_to")
    inlines = [MessageInline]


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "case", "sender", "is_ai", "created_at")
    list_filter = ("is_ai",)
    raw_id_fields = ("case", "sender")
