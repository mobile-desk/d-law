from django.urls import path

from cases.views import (
    assignment_intake,
    case_assign,
    case_detail,
    case_list,
    case_share_access,
    lawyer_case_action,
)

app_name = "cases"

urlpatterns = [
    path("", case_list, name="list"),
    path("link/<uuid:share_token>/", case_share_access, name="share_access"),
    path("<int:case_id>/", case_detail, name="detail"),
    path("<int:case_id>/assignment-intake/", assignment_intake, name="assignment_intake"),
    path("<int:case_id>/assign/", case_assign, name="assign"),
    path("<int:case_id>/lawyer-action/", lawyer_case_action, name="lawyer_action"),
]
