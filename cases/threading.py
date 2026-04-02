"""
Split “intake / Guide chat” messages from the lawyer ↔ client thread.
"""

from __future__ import annotations

from cases.models import Case, Message

THREAD_INTAKE = "intake"
THREAD_PROFESSIONAL = "professional"


def first_lawyer_message(case: Case) -> Message | None:
    if not case.assigned_to_id:
        return None
    return (
        Message.objects.filter(case=case, is_ai=False, sender_id=case.assigned_to_id)
        .order_by("created_at")
        .first()
    )


def is_professional_human_message(
    case: Case,
    m: Message,
    *,
    t0=None,
    first_law: Message | None = None,
) -> bool:
    if m.is_ai:
        return False
    if m.metadata.get("thread") == THREAD_PROFESSIONAL:
        return True
    if m.metadata.get("thread") == THREAD_INTAKE:
        return False
    if case.assigned_to_id and m.sender_id == case.assigned_to_id:
        return True
    if not case.assigned_to_id:
        return False
    if first_law is None:
        first_law = first_lawyer_message(case)
    t0 = first_law.created_at if first_law else None
    if not t0:
        # Before the lawyer’s first message, only explicit professional tags count (new messages are tagged).
        return False
    if m.created_at >= t0:
        if m.sender_id == case.user_id:
            return True
        if m.sender_id is None:
            return True
    return False


def professional_thread_messages(case: Case) -> list[Message]:
    """Human lawyer ↔ client only (excludes AI Guide and intake user lines)."""
    first_law = first_lawyer_message(case)
    t0 = first_law.created_at if first_law else None
    rows = list(Message.objects.filter(case=case, is_ai=False).select_related("sender").order_by("created_at"))
    return [m for m in rows if is_professional_human_message(case, m, t0=t0, first_law=first_law)]


def intake_thread_messages(case: Case) -> list[Message]:
    """Guide chat + client intake lines (everything not in the professional human thread)."""
    first_law = first_lawyer_message(case)
    t0 = first_law.created_at if first_law else None
    rows = list(Message.objects.filter(case=case).select_related("sender").order_by("created_at"))
    return [
        m
        for m in rows
        if m.is_ai or not is_professional_human_message(case, m, t0=t0, first_law=first_law)
    ]
