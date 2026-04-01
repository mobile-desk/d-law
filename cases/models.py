import uuid

from django.conf import settings
from django.db import models


class Case(models.Model):
    STATUS_CHOICES = (
        ("pending", "Pending"),
        ("assigned", "Assigned"),
        ("in_progress", "In Progress"),
        ("closed", "Closed"),
        ("rejected_by_professional", "Rejected by professional"),
    )

    guest_session_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        db_index=True,
        help_text="Anonymous users track cases via this id before signing up.",
    )
    share_token = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
        db_index=True,
        help_text="Secret link for anonymous clients (email / share); not the numeric case id.",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="client_cases",
    )
    description = models.TextField(blank=True)
    category = models.CharField(max_length=255, blank=True)
    ai_classified_category = models.CharField(max_length=255, blank=True)
    intake_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured answers: what, where, when, who, etc.",
    )
    is_anonymous = models.BooleanField(default=True)

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="cases",
    )
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default="pending")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Cases"

    def __str__(self):
        return f"Case #{self.pk} — {self.status}"


class Message(models.Model):
    case = models.ForeignKey(Case, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="case_messages",
    )
    content = models.TextField()
    is_ai = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        prefix = "AI" if self.is_ai else (self.sender_id or "anon")
        return f"{prefix}: {self.content[:40]}…"
