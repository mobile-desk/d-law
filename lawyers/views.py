from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from cases.models import Case, Message
from cases.permissions import user_is_assigned_professional


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
            )
        return redirect("lawyers:case", case_id=case.pk)

    msgs = case.messages.select_related("sender").order_by("created_at")
    return render(
        request,
        "lawyers/case_detail.html",
        {
            "case": case,
            "case_messages": msgs,
            "category_label": _lawyer_case_category_label(case),
        },
    )
