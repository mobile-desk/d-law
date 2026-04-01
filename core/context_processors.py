"""Expose one-shot MVP toast data (popped each render)."""


def mvp_client_toast(request):
    return {
        "mvp_client_reply_copy_url": request.session.pop("mvp_client_reply_copy_url", None),
        "mvp_client_reply_email_hint": request.session.pop("mvp_client_reply_email_hint", None),
    }
