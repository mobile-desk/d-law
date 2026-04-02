from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from cases.assignment_intake import assignment_detail_rows_for_lawyer
from cases.client_notify import maybe_queue_anonymous_reply_toast
from cases.models import Case, Message
from cases.permissions import user_is_assigned_professional
from cases.threading import intake_thread_messages, professional_thread_messages
from chatbot.services import refresh_intake_conversation_summary


def _lawyer_case_category_label(case: Case) -> str:
    raw = (case.category or case.ai_classified_category or "").strip()
    if not raw:
        return ""
    return raw.replace("_", " ").replace("-", " ").title()


@login_required
def lawyer_dashboard(request):
    if request.user.user_type not in ("lawyer", "activist") and not request.user.is_staff:
        return HttpResponseForbidden("This area is for verified professionals.")

    qs = Case.objects.filter(assigned_to=request.user).order_by("-created_at")
    status = request.GET.get("status")
    if status:
        qs = qs.filter(status=status)
    return render(
        request,
        "lawyers/dashboard.html",
        {"cases": qs, "filter_status": status or ""},
    )


@login_required
def lawyer_case_detail(request, case_id):
    case = get_object_or_404(Case.objects.select_related("assigned_to", "user").prefetch_related("messages"), pk=case_id)
    if not request.user.is_staff and not user_is_assigned_professional(request, case):
        return HttpResponseForbidden("You are not assigned to this case.")

    if request.method == "POST":
        body = (request.POST.get("content") or "").strip()
        if body:
            Message.objects.create(
                case=case,
                sender=request.user,
                content=body,
                is_ai=False,
                metadata={"thread": "professional"},
            )
            maybe_queue_anonymous_reply_toast(request, case, request.user)
        return redirect("lawyers:case", case_id=case.pk)

    case_human_messages = professional_thread_messages(case)
    if not (case.intake_chat_summary or "").strip() and intake_thread_messages(case):
        refresh_intake_conversation_summary(case)
        case.refresh_from_db()
    client_share_url = request.build_absolute_uri(
        reverse("cases:share_access", kwargs={"share_token": case.share_token})
    )
    return render(
        request,
        "lawyers/case_detail.html",
        {
            "case": case,
            "case_human_messages": case_human_messages,
            "category_label": _lawyer_case_category_label(case),
            "assignment_detail_rows": assignment_detail_rows_for_lawyer(case),
            "client_share_url": client_share_url,
        },
    )
