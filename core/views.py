from django.contrib.auth import get_user_model
from django.shortcuts import render


def home(request):
    return render(request, "core/home.html")


def product(request):
    return render(request, "core/product.html")


def quick_cards(request):
    return render(request, "core/quick_cards.html")


def emergency(request):
    return render(request, "core/emergency.html")


def report_incidents(request):
    return render(request, "core/report.html")


def health(request):
    from django.http import JsonResponse

    return JsonResponse({"status": "ok"})


def lawyers_directory(request):
    User = get_user_model()
    lawyers = (
        User.objects.filter(user_type="lawyer")
        .order_by("last_name", "first_name", "email")
        .only("first_name", "last_name", "email")
    )
    return render(request, "core/lawyers_list.html", {"lawyers": lawyers})
