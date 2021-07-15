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
    # ex: /ZuwX4mKCPgK06sIin8QJxQ/
    path("<uid>/", views.DetailView.as_view(), name="detail"),
    # ex: /ZuwX4mKCPgK06sIin8QJxQ/edit
    path("<uid>/edit", views.EditView.as_view(), name="edit"),
    # ex: /ZuwX4mKCPgK06sIin8QJxQ/sync
    path("<uid>/sync", views.SyncView.as_view(), name="sync"),
    # ex: /ZuwX4mKCPgK06sIin8QJxQ/rider_search
    path("<uid>/rider_search", views.RiderSearchView.as_view(), name="rider_search"),
    # ex: /ZuwX4mKCPgK06sIin8QJxQ/teams
    path("<uid>/teams", views.EditTeamsView.as_view(), name="teams"),
    # ex: /ZuwX4mKCPgK06sIin8QJxQ/teams/bulk
    path("<uid>/teams/bulk", views.UpdateTeamsView.as_view(), name="update_teams"),
    # ex: /ZuwX4mKCPgK06sIin8QJxQ/rides
    path("<uid>/rides", views.EditRidesView.as_view(), name="rides"),
    # ex: /ZuwX4mKCPgK06sIin8QJxQ/rides/filters
    path("<uid>/rides/filters", views.RideFiltersView.as_view(), name="ride_filters"),
    # ex: /ZuwX4mKCPgK06sIin8QJxQ/permissions
    path(
        "<uid>/permissions", views.UpdatePermissionsView.as_view(), name="permissions"
    ),
]
