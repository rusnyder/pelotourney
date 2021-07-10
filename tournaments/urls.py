from django.urls import path

from . import views

app_name = "tournaments"
urlpatterns = [
    # ex: /tournaments/
    path("", views.IndexView.as_view(), name="index"),
    # ex: /tournaments/authorize
    path("authorize/", views.LinkProfileView.as_view(), name="authorize"),
    # ex: /tournaments/5/
    path("<int:pk>/", views.DetailView.as_view(), name="detail"),
    # ex: /tournaments/5/sync
    path("<int:pk>/sync", views.SyncView.as_view(), name="sync"),
]
