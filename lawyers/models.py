from django.conf import settings
from django.db import models


class LawyerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="lawyer_profile",
    )
    specialization = models.CharField(max_length=255)
    years_experience = models.PositiveIntegerField(default=0)
    location = models.CharField(max_length=255, blank=True)
    is_available = models.BooleanField(default=True)
    rating = models.FloatField(default=0.0)
    bio = models.TextField(blank=True)

    class Meta:
        ordering = ["-rating", "pk"]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} — {self.specialization}"


class VerificationDocument(models.Model):
    """ID and bar license (or NGO proof) for lawyer/activist verification."""

    DOC_TYPE_CHOICES = (
        ("government_id", "Government ID"),
        ("bar_license", "Bar license / professional credential"),
        ("other", "Other supporting document"),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_documents",
    )
    document_type = models.CharField(max_length=32, choices=DOC_TYPE_CHOICES)
    file = models.FileField(upload_to="verification/%Y/%m/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    approved = models.BooleanField(null=True, blank=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.user.email} — {self.get_document_type_display()}"
