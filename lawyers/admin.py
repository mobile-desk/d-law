from django.contrib import admin

from lawyers.models import LawyerProfile, VerificationDocument


@admin.register(LawyerProfile)
class LawyerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "specialization", "location", "is_available", "rating")
    list_filter = ("is_available",)
    search_fields = ("user__email", "specialization", "location")
    raw_id_fields = ("user",)


@admin.register(VerificationDocument)
class VerificationDocumentAdmin(admin.ModelAdmin):
    list_display = ("user", "document_type", "uploaded_at", "approved")
    list_filter = ("document_type", "approved")
    raw_id_fields = ("user",)
