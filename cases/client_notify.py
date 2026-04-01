"""MVP: when a professional replies to an anonymous client, queue a copyable share link (email later)."""

from __future__ import annotations

from django.urls import reverse


def anonymous_client_email(case) -> str:
    details = (case.intake_data or {}).get("assignment_details") or {}
    return (details.get("contact_email") or "").strip()


def maybe_queue_anonymous_reply_toast(request, case, sender) -> None:
    """
    If the assigned professional replied and the case has no linked client account,
    store the magic link in session for a copy-toast on the next page (SMTP not wired yet).
    """
    if case.user_id is not None:
        return
    if not case.assigned_to_id or case.assigned_to_id != sender.id:
        return
    url = request.build_absolute_uri(
        reverse("cases:share_access", kwargs={"share_token": case.share_token})
    )
    request.session["mvp_client_reply_copy_url"] = url
    email = anonymous_client_email(case)
    if email:
        request.session["mvp_client_reply_email_hint"] = email
