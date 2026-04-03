from django.urls import path

from core.views import emergency, health, home, lawyers_directory, product, quick_cards, report_incidents

urlpatterns = [
    path("", home, name="home"),
    path("lawyers/", lawyers_directory, name="lawyers_directory"),
    path("product/", product, name="product"),
    path("quick-cards/", quick_cards, name="quick_cards"),
    path("emergency/", emergency, name="emergency"),
    path("report/", report_incidents, name="report"),
    path("health/", health, name="health"),
]
