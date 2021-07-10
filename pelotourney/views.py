from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout as log_out
from django.http import HttpResponseRedirect
from django.shortcuts import redirect, render, reverse


def index(request):
    user = request.user
    if user.is_authenticated:
        return redirect(reverse("tournaments:index"))
    else:
        return render(request, "index.html")


def logout(request):
    log_out(request)
    return_to = urlencode({"returnTo": request.build_absolute_uri("/")})
    logout_url = "https://{}/v2/logout?client_id={}&{}".format(
        settings.SOCIAL_AUTH_AUTH0_DOMAIN,
        settings.SOCIAL_AUTH_AUTH0_KEY,
        return_to,
    )
    return HttpResponseRedirect(logout_url)
