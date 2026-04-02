from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from cases.models import Case
from cases.permissions import user_can_access_case
from chatbot.services import llm_configured, process_intake_post


def intake_start(request):
    """Create anonymous case and store guest session; redirect to chat."""
    case = Case.objects.create(description="", is_anonymous=True)
    request.session["guest_case_id"] = case.id
    request.session["guest_session_id"] = str(case.guest_session_id)
    return redirect("chatbot:chat", case_id=case.pk)


@require_http_methods(["GET", "POST"])
def chat_view(request, case_id):
    case = get_object_or_404(Case, pk=case_id)
    if not user_can_access_case(request, case):
        return HttpResponseForbidden("You cannot access this conversation.")

    if request.method == "POST":
        content = request.POST.get("content", "").strip()
        if content:
            sender = request.user if request.user.is_authenticated else None
            process_intake_post(case, content, sender=sender)
        return redirect("chatbot:chat", case_id=case.pk)

    ctx = {
        "case": case,
        "chat_messages": case.messages.select_related("sender").order_by("created_at"),
        "show_assignment_cta": False,
        "llm_configured": llm_configured(),
    }
    last_ai = case.messages.filter(is_ai=True).order_by("-created_at").first()
    if last_ai and last_ai.metadata.get("show_assignment_cta"):
        ctx["show_assignment_cta"] = True
    return render(request, "chatbot/chat.html", ctx)
