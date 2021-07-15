from django.urls import path

from . import views

app_name = "tournaments"
urlpatterns = [
    # ex: /tournaments/
    path("", views.IndexView.as_view(), name="index"),
    # ex: /tournaments/new
    path("new/", views.CreateView.as_view(), name="create"),
    # ex: /tournaments/authorize
    path("authorize/", views.LinkProfileView.as_view(), name="authorize"),
    # ex: /tournaments/5/
    path("<int:pk>/", views.DetailView.as_view(), name="detail"),
    # ex: /tournaments/5/edit
    path("<int:pk>/edit", views.EditView.as_view(), name="edit"),
    # ex: /tournaments/5/sync
    path("<int:pk>/sync", views.SyncView.as_view(), name="sync"),
    # ex: /tournaments/5/rider_search
    path("<int:pk>/rider_search", views.RiderSearchView.as_view(), name="rider_search"),
    # ex: /tournaments/5/teams
    path("<int:pk>/teams", views.EditTeamsView.as_view(), name="teams"),
    # ex: /tournaments/5/teams/bulk
    path(
        "<int:pk>/teams/bulk", views.BulkUpdateTeamsView.as_view(), name="update_teams"
    ),
    # ex: /tournaments/5/rides
    path("<int:pk>/rides", views.EditRidesView.as_view(), name="rides"),
    # ex: /tournaments/5/rides/filters
    path(
        "<int:pk>/rides/filters", views.RideFiltersView.as_view(), name="ride_filters"
    ),
]
