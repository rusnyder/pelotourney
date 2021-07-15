"""pelotourney URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path

from . import settings
from .views import index, logout

app_name = "pelotourney"
urlpatterns = [
    path("", index),
    path("logout", logout, name="logout_custom"),
    path("tournaments/", include("tournaments.urls")),
    path("accounts/", include("django.contrib.auth.urls")),
    path("social/", include("social_django.urls")),
    path("admin/", admin.site.urls),
]
if settings.debug_toolbar:
    urlpatterns.append(path("__debug__/", include(settings.debug_toolbar.urls)))
