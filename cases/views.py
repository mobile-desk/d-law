from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from cases.models import Case, Message
from cases.permissions import guest_session_matches, user_can_access_case, user_is_assigned_professional
from matching.engine import assign_case, lawyer_accept_case, lawyer_reject_case


def _case_category_label(case: Case) -> str:
    raw = (case.category or case.ai_classified_category or "").strip()
    if not raw:
        return ""
    return raw.replace("_", " ").replace("-", " ").title()


@login_required
def case_list(request):
    qs = (
        Case.objects.filter(Q(user=request.user) | Q(assigned_to=request.user))
        .distinct()
        .order_by("-created_at")
    )
    return render(request, "cases/list.html", {"cases": qs})


@require_http_methods(["GET", "POST"])
def case_detail(request, case_id):
    case = get_object_or_404(
        Case.objects.select_related("assigned_to", "user"),
        pk=case_id,
    )
    if not user_can_access_case(request, case):
        return HttpResponseForbidden("You cannot view this case.")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "claim" and request.user.is_authenticated and not case.user_id:
            gid = request.session.get("guest_session_id")
            if gid and guest_session_matches(case, gid):
                case.user = request.user
                case.is_anonymous = False
                case.save(update_fields=["user", "is_anonymous", "updated_at"])
                request.session.pop("guest_case_id", None)
                request.session.pop("guest_session_id", None)
                messages.success(request, "This case is now linked to your account.")
            return redirect("cases:detail", case_id=case.pk)

        if action == "human_message" and request.user.is_authenticated and case.assigned_to_id:
            body = (request.POST.get("content") or "").strip()
            if body and (case.user_id == request.user.id or case.assigned_to_id == request.user.id):
                Message.objects.create(
                    case=case,
                    sender=request.user,
                    content=body,
                    is_ai=False,
                )
            return redirect("cases:detail", case_id=case.pk)

    gid = request.session.get("guest_session_id")
    can_claim = (
        request.user.is_authenticated
        and not case.user_id
        and gid
        and guest_session_matches(case, gid)
    )
    can_human_chat = (
        case.assigned_to_id
        and request.user.is_authenticated
        and (case.user_id == request.user.id or case.assigned_to_id == request.user.id)
        and case.status in ("assigned", "in_progress")
    )
    if user_is_assigned_professional(request, case):
        case_viewer_role = "professional"
    elif case.user_id and case.user_id == request.user.id:
        case_viewer_role = "client"
    elif request.user.is_staff:
        case_viewer_role = "staff"
    else:
        case_viewer_role = "client"

    return render(
        request,
        "cases/detail.html",
        {
            "case": case,
            "can_claim": can_claim,
            "can_human_chat": can_human_chat,
            "category_label": _case_category_label(case),
            "case_viewer_role": case_viewer_role,
        },
    )


@require_http_methods(["GET", "POST"])
def case_assign(request, case_id):
    case = get_object_or_404(Case, pk=case_id)
    if not user_can_access_case(request, case):
        return HttpResponseForbidden("You cannot request assignment for this case.")

    if request.method == "POST":
        ok = assign_case(case)
        case.refresh_from_db()
        if ok:
            messages.success(request, "We’ve matched you with a professional. They’ll review your case.")
        else:
            messages.warning(
                request,
                "No verified professional is available for this category yet. Please try again later or contact support.",
            )
        return redirect("cases:detail", case_id=case.pk)

    return redirect("cases:detail", case_id=case.pk)


@login_required
@require_http_methods(["POST"])
def lawyer_case_action(request, case_id):
    case = get_object_or_404(Case, pk=case_id)
    if not user_is_assigned_professional(request, case):
        return HttpResponseForbidden("Not assigned to you.")

    act = request.POST.get("action")
    if act == "accept":
        lawyer_accept_case(case, request.user)
        messages.success(request, "Case accepted.")
    elif act == "reject":
        lawyer_reject_case(case, request.user)
        messages.info(request, "Case returned to the pool.")
    elif act == "close":
        case.status = "closed"
        case.save(update_fields=["status", "updated_at"])
        messages.success(request, "Case closed.")
    return redirect("lawyers:case", case_id=case.pk)
