from uuid import UUID


def guest_session_matches(case, guest_session_id) -> bool:
    if not guest_session_id:
        return False
    try:
        return case.guest_session_id == UUID(str(guest_session_id))
    except (ValueError, TypeError):
        return False


def user_can_access_case(request, case) -> bool:
    """Staff, client, assigned professional, or anonymous guest with matching session."""
    user = request.user
    if user.is_staff:
        return True
    if case.user_id and user.is_authenticated and case.user_id == user.id:
        return True
    if case.assigned_to_id and user.is_authenticated and case.assigned_to_id == user.id:
        return True
    gid = request.session.get("guest_session_id")
    if gid and guest_session_matches(case, gid):
        return True
    return False


def user_is_assigned_professional(request, case) -> bool:
    return (
        request.user.is_authenticated
        and case.assigned_to_id
        and case.assigned_to_id == request.user.id
    )
