from django.urls import path

from cases.views import case_assign, case_detail, case_list, lawyer_case_action

app_name = "cases"

urlpatterns = [
    path("", case_list, name="list"),
    path("<int:case_id>/", case_detail, name="detail"),
    path("<int:case_id>/assign/", case_assign, name="assign"),
    path("<int:case_id>/lawyer-action/", lawyer_case_action, name="lawyer_action"),
]
