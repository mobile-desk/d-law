"""
Case → lawyer/activist assignment (v1: category + rating).

Intake stores categories as slugs (e.g. police_abuse, civil) from chatbot.services;
lawyer profiles use human-readable specialization strings. We map slugs → OR filters
on specialization; if none match, fall back to any verified available professional.
"""

from django.db import transaction
from django.db.models import Q

from lawyers.models import LawyerProfile
from notifications.services import notify_user


def _normalize_category_slug(raw: str) -> str:
    return (raw or "").strip().lower().replace(" ", "_")


def _specialization_q_for_slug(slug: str) -> Q:
    """
    Map intake category slugs (aligned with chatbot.services.CATEGORIES) to
    LawyerProfile.specialization substring matches.
    """
    if not slug:
        return Q()

    # Slug → substrings matched with icontains (OR). "general" = no extra filter.
    slug_map: dict[str, Q] = {
        "police_abuse": (
            Q(specialization__icontains="Criminal")
            | Q(specialization__icontains="Human rights")
            | Q(specialization__icontains="Civil")
        ),
        "criminal": Q(specialization__icontains="Criminal"),
        "civil": (
            Q(specialization__icontains="Civil")
            | Q(specialization__icontains="Housing")
            | Q(specialization__icontains="Employment")
            | Q(specialization__icontains="Commercial")
            | Q(specialization__icontains="Property")
            | Q(specialization__icontains="Family")
        ),
        "domestic_violence": (
            Q(specialization__icontains="Family")
            | Q(specialization__icontains="Human rights")
        ),
        "human_rights": Q(specialization__icontains="Human rights"),
        "general": Q(),
    }

    if slug in slug_map:
        return slug_map[slug]

    # Legacy / manual category set to a full specialization title
    return Q(specialization__iexact=slug) | Q(specialization__icontains=slug)


def assign_case(case):
    """
    Assign first matching verified professional by specialization (category slug)
    and rating. Returns True if assigned.
    """
    category = (case.category or case.ai_classified_category or "").strip()
    if not category:
        return False

    slug = _normalize_category_slug(category)

    base = LawyerProfile.objects.filter(
        is_available=True,
        user__is_verified=True,
    ).filter(Q(user__user_type="lawyer") | Q(user__user_type="activist"))

    spec_q = _specialization_q_for_slug(slug)
    qs = (
        base.filter(spec_q)
        .select_related("user")
        .order_by("-rating", "-pk")
    )

    lawyer_profile = qs.first()
    if not lawyer_profile:
        lawyer_profile = (
            base.select_related("user").order_by("-rating", "-pk").first()
        )
    if not lawyer_profile:
        return False

    with transaction.atomic():
        case.assigned_to = lawyer_profile.user
        case.status = "assigned"
        case.save(update_fields=["assigned_to", "status", "updated_at"])

    notify_user(
        lawyer_profile.user,
        title="New case assigned",
        body=f"You have a new case (#{case.pk}). Please accept or reject in your dashboard.",
        related_case_id=case.pk,
    )
    if case.user_id:
        notify_user(
            case.user,
            title="A professional has been assigned",
            body="Your case has been matched. You will be notified when they respond.",
            related_case_id=case.pk,
        )
    return True


def lawyer_accept_case(case, user):
    if case.assigned_to_id != user.id:
        return False, "Not your assignment."
    case.status = "in_progress"
    case.save(update_fields=["status", "updated_at"])
    if case.user_id:
        notify_user(
            case.user,
            title="Case in progress",
            body=f"Your case #{case.pk} is now in progress.",
            related_case_id=case.pk,
        )
    return True, None


def lawyer_reject_case(case, user):
    if case.assigned_to_id != user.id:
        return False, "Not your assignment."
    case.assigned_to = None
    case.status = "pending"
    case.save(update_fields=["assigned_to", "status", "updated_at"])
    return True, None
