from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from cases.assignment_intake import assignment_detail_rows_for_lawyer
from cases.models import Case, Message
from cases.permissions import (
    guest_session_matches,
    needs_assignment_intake_redirect,
    user_can_access_case,
    user_is_assigned_professional,
)
from cases.client_notify import maybe_queue_anonymous_reply_toast
from cases.threading import intake_thread_messages, professional_thread_messages
from chatbot.services import refresh_intake_conversation_summary
from matching.engine import assign_case, lawyer_accept_case, lawyer_reject_case


@require_http_methods(["GET"])
def case_share_access(request, share_token):
    """
    Magic link for anonymous clients: sets guest session and opens the case (numeric id in URL after redirect).
    """
    case = get_object_or_404(Case, share_token=share_token)
    request.session["guest_session_id"] = str(case.guest_session_id)
    messages.info(request, "Opened with your private link. Save this URL or create an account to keep access.")
    return redirect("cases:detail", case_id=case.pk)


def _case_category_label(case: Case) -> str:
    raw = (case.category or case.ai_classified_category or "").strip()
    if not raw:
        return ""
    return raw.replace("_", " ").replace("-", " ").title()


def _can_human_chat(request, case) -> bool:
    """Logged-in client/lawyer, or anonymous guest with matching session (private link)."""
    if not case.assigned_to_id or case.status not in ("assigned", "in_progress"):
        return False
    if request.user.is_authenticated:
        return case.user_id == request.user.id or case.assigned_to_id == request.user.id
    if case.user_id:
        return False
    gid = request.session.get("guest_session_id")
    return bool(gid and guest_session_matches(case, gid))


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

        if action == "human_message" and case.assigned_to_id:
            body = (request.POST.get("content") or "").strip()
            if body and request.user.is_authenticated:
                if case.user_id == request.user.id or case.assigned_to_id == request.user.id:
                    Message.objects.create(
                        case=case,
                        sender=request.user,
                        content=body,
                        is_ai=False,
                        metadata={"thread": "professional"},
                    )
                    if not case.user_id and case.assigned_to_id == request.user.id:
                        maybe_queue_anonymous_reply_toast(request, case, request.user)
            elif body and not case.user_id and not request.user.is_authenticated:
                gid = request.session.get("guest_session_id")
                if (
                    gid
                    and guest_session_matches(case, gid)
                    and case.status in ("assigned", "in_progress")
                ):
                    Message.objects.create(
                        case=case,
                        sender=None,
                        content=body,
                        is_ai=False,
                        metadata={"thread": "professional"},
                    )
            return redirect("cases:detail", case_id=case.pk)

    if needs_assignment_intake_redirect(request, case):
        return redirect("cases:assignment_intake", case_id=case.pk)

    gid = request.session.get("guest_session_id")
    can_claim = (
        request.user.is_authenticated
        and not case.user_id
        and gid
        and guest_session_matches(case, gid)
    )
    can_human_chat = _can_human_chat(request, case)
    if user_is_assigned_professional(request, case):
        case_viewer_role = "professional"
    elif case.user_id and case.user_id == request.user.id:
        case_viewer_role = "client"
    elif request.user.is_staff:
        case_viewer_role = "staff"
    else:
        case_viewer_role = "client"

    show_assignment_rows = user_is_assigned_professional(request, case) or request.user.is_staff
    case_human_messages = professional_thread_messages(case)
    if not (case.intake_chat_summary or "").strip() and intake_thread_messages(case):
        refresh_intake_conversation_summary(case)
        case.refresh_from_db()
    return render(
        request,
        "cases/detail.html",
        {
            "case": case,
            "can_claim": can_claim,
            "can_human_chat": can_human_chat,
            "category_label": _case_category_label(case),
            "case_viewer_role": case_viewer_role,
            "case_human_messages": case_human_messages,
            "assignment_detail_rows": (
                assignment_detail_rows_for_lawyer(case) if show_assignment_rows else []
            ),
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
        if ok and needs_assignment_intake_redirect(request, case):
            return redirect("cases:assignment_intake", case_id=case.pk)
        return redirect("cases:detail", case_id=case.pk)

    return redirect("cases:detail", case_id=case.pk)


@require_http_methods(["GET", "POST"])
def assignment_intake(request, case_id):
    case = get_object_or_404(Case.objects.select_related("assigned_to", "user"), pk=case_id)
    if not user_can_access_case(request, case):
        return HttpResponseForbidden("You cannot access this case.")

    if request.user.is_staff or user_is_assigned_professional(request, case):
        return redirect("cases:detail", case_id=case.pk)

    if not (case.assigned_to_id and case.status in ("assigned", "in_progress")):
        return redirect("cases:detail", case_id=case.pk)

    from cases.assignment_intake import (
        assignment_intake_complete,
        category_slug_for_case,
        field_rows_with_values,
        fields_for_case,
        merge_assignment_details,
        validate_post,
    )

    if request.method == "GET" and assignment_intake_complete(case, request):
        return redirect("cases:detail", case_id=case.pk)

    if request.method == "POST":
        posted = {f["name"]: (request.POST.get(f["name"]) or "") for f in fields_for_case(case, request)}
        ok, errors, cleaned = validate_post(case, request, posted)
        if ok:
            merge_assignment_details(case, cleaned)
            messages.success(request, "Thanks — your lawyer has the details they need to help you.")
            return redirect("cases:detail", case_id=case.pk)
        return render(
            request,
            "cases/assignment_intake.html",
            {
                "case": case,
                "field_rows": field_rows_with_values(case, request, posted=posted),
                "category_slug": category_slug_for_case(case),
                "errors": errors,
            },
        )

    return render(
        request,
        "cases/assignment_intake.html",
        {
            "case": case,
            "field_rows": field_rows_with_values(case, request),
            "category_slug": category_slug_for_case(case),
            "errors": [],
        },
    )


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
