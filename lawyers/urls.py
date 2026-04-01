from django.urls import path

from lawyers.views import lawyer_case_detail, lawyer_dashboard

app_name = "lawyers"

urlpatterns = [
    path("", lawyer_dashboard, name="dashboard"),
    path("cases/<int:case_id>/", lawyer_case_detail, name="case"),
]
