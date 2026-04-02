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
