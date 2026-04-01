from django.shortcuts import render


def home(request):
    return render(request, "core/home.html")


def health(request):
    from django.http import JsonResponse

    return JsonResponse({"status": "ok"})
