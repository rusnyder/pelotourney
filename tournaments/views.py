import json
from datetime import datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseNotFound, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import dateparse, timezone
from django.views import generic

from .external.peloton import BadCredentials, NotAuthenticated, PelotonClient
from .models import (
    PelotonProfile,
    Ride,
    Tournament,
    TournamentMember,
    TournamentRide,
    TournamentTeam,
    Workout,
)


class IndexView(LoginRequiredMixin, generic.View):
    def get(self, request):
        now = datetime.utcnow()
        tournaments = {}
        if hasattr(request.user, "profile"):
            common_filters = {"participants": self.request.user.profile}
            tournaments["upcoming"] = Tournament.objects.filter(
                start_date__gt=now,
                start_date__lte=now + timedelta(weeks=2),
                **common_filters,
            ).order_by("-start_date")
            tournaments["active"] = Tournament.objects.filter(
                start_date__lte=now,
                end_date__gte=now,
                **common_filters,
            ).order_by("-start_date")
            tournaments["recent"] = Tournament.objects.filter(
                end_date__lt=now,
                end_date__gte=now - timedelta(weeks=2),
                **common_filters,
            ).order_by("-start_date")
        context = {"tournaments": tournaments}
        return render(request, "tournaments/index.html", context)


class CreateView(generic.View):
    def get(self, request):
        return render(request, "tournaments/new.html")

    def post(self, request):
        start_date = datetime.combine(
            dateparse.parse_date(request.POST["start_date"]),
            dateparse.parse_time("00:00:00.000"),
        )
        end_date = datetime.combine(
            dateparse.parse_date(request.POST["end_date"]),
            dateparse.parse_time("11:59:59.999"),
        )
        tournament = Tournament.objects.create(
            name=request.POST["tournament_name"],
            format=Tournament.Format.SIMPLE,
            start_date=timezone.utc.localize(start_date),
            end_date=timezone.utc.localize(end_date),
            visibility=request.POST["visibility"],
        )
        TournamentMember.objects.create(
            tournament=tournament,
            peloton_profile=request.user.profile,
            role=TournamentMember.Role.OWNER,
        )
        return redirect("tournaments:detail", tournament.uid)


class DetailView(generic.View):
    def get(self, request, uid):
        tournament = get_object_or_404(Tournament, uid=uid)
        if not (
            tournament.visibility == Tournament.Visibility.PUBLIC
            or request.user.is_authenticated
        ):
            raise PermissionDenied()
        context = {"tournament": tournament}
        return render(request, "tournaments/detail.html", context)


class EditView(LoginRequiredMixin, generic.View):
    SETTINGS_TABS = {"settings", "rides", "teams", "permissions"}

    def get(self, request, uid, tab=None):
        # Redirect to the default settings tab (keeps URL consistent)
        if not tab:
            return redirect("tournaments:edit", uid, "settings")
        elif tab not in self.SETTINGS_TABS:
            return HttpResponseNotFound()

        tournament = get_object_or_404(Tournament, uid=uid)
        if request.user.profile not in tournament.admins:
            raise PermissionDenied()
        context = {"tournament": tournament, "settings_tab": tab}
        return render(request, "tournaments/edit.html", context)

    def post(self, request, uid, tab=None):
        tournament = get_object_or_404(Tournament, uid=uid)
        if request.user.profile not in tournament.admins:
            raise PermissionDenied()

        if tab and tab not in self.SETTINGS_TABS:
            return HttpResponseNotFound()

        # Save all form fields again (even if it's a noop, this is just easier)
        start_date = datetime.combine(
            dateparse.parse_date(request.POST["start_date"]),
            dateparse.parse_time("00:00:00.000"),
        )
        end_date = datetime.combine(
            dateparse.parse_date(request.POST["end_date"]),
            dateparse.parse_time("11:59:59.999"),
        )
        tournament.name = request.POST["tournament_name"]
        tournament.start_date = timezone.utc.localize(start_date)
        tournament.end_date = timezone.utc.localize(end_date)
        tournament.visibility = request.POST["visibility"]
        tournament.save()

        # Redirect to either the tournament page (new) or setting (edit)
        return redirect("tournaments:detail", tournament.uid)


class SyncView(LoginRequiredMixin, generic.View):
    def post(self, request, uid):
        # Ensure the tournament exists
        tournament = get_object_or_404(Tournament, uid=uid)
        if request.user.profile not in tournament.admins:
            raise PermissionDenied()

        # Create a client logged into the Peloton API
        profile = request.user.profile
        client = PelotonClient()
        try:
            if profile.peloton_session_id:
                client.load_session(profile.peloton_session_id)
        except NotAuthenticated:
            pass

        # Sync the rides (updates ride metadata, regardless of activity or participants)
        for ride in tournament.rides.all():
            ride.update_from_api(client)
            ride.save()

        # Sync all relevant workouts from this tournament
        for participant in tournament.participants.all():
            # Sync user first (updates profile metadata)
            participant.update_from_api(client)
            participant.save()

            # Then download the workouts
            workouts = client.get_workouts(
                user_id=participant.peloton_id,
                start_date=tournament.start_date,
                # TODO[RWS]: HACK!  This is covering for two bugs:
                #   1. The end date is set to noon, not midnight (+12)
                #   2. The start/end dates are non-configurably anchored in UTC (+5)
                end_date=tournament.end_date + timedelta(hours=17),
                ride_ids=tournament.rides.values_list("peloton_id", flat=True),
            )
            for workout_data in workouts:
                Workout.from_peloton_id(workout_data["id"], client)

        # Redirect back to the tournament page
        tournament.last_synced = datetime.utcnow()
        tournament.save()
        return redirect("tournaments:detail", tournament.uid)


class RiderSearchView(LoginRequiredMixin, generic.View):
    def get(self, request, uid):
        # Search for riders
        client = _get_client(request)
        riders = client.search_users(request.GET["rider_query"])
        return JsonResponse(riders, safe=False)

    def post(self, request, uid):
        tournament = get_object_or_404(Tournament, uid=uid)
        if request.user.profile not in tournament.admins:
            raise PermissionDenied()

        username = request.POST["rider_query"]
        client = _get_client(request)
        profile = PelotonProfile.from_peloton_id_or_username(
            peloton_id="",
            username=username,
            client=client,
        )
        if profile not in tournament.participants.all():
            TournamentMember.objects.create(
                tournament=tournament,
                peloton_profile=profile,
                role=TournamentMember.Role.MEMBER,
            )

        return redirect("tournaments:edit", uid, "teams")

    def delete(self, request, uid):
        tournament = get_object_or_404(Tournament, uid=uid)
        if request.user.profile not in tournament.admins.all():
            raise PermissionDenied()

        username = request.body.decode(request.encoding)
        TournamentMember.objects.filter(
            tournament=tournament,
            peloton_profile__username=username,
        ).delete()
        return HttpResponse(status=204)


class EditTeamsView(LoginRequiredMixin, generic.View):
    def post(self, request, uid):
        tournament = get_object_or_404(Tournament, uid=uid)
        if request.user.profile not in tournament.admins.all():
            raise PermissionDenied()

        team_name = request.POST["new_team_name"]
        TournamentTeam.objects.create(
            tournament=tournament,
            name=team_name,
        )
        return redirect("tournaments:edit", uid, "teams")

    def delete(self, request, uid):
        tournament = get_object_or_404(Tournament, uid=uid)
        if request.user.profile not in tournament.admins.all():
            raise PermissionDenied()

        # Delete the team (cascade for members is setup to unassign them)
        team_id = request.body.decode(request.encoding)
        TournamentTeam.objects.filter(id=team_id).delete()
        return HttpResponse(status=204)


class UpdateTeamsView(LoginRequiredMixin, generic.View):
    def post(self, request, uid):
        tournament = get_object_or_404(Tournament, uid=uid)
        if request.user.profile not in tournament.admins.all():
            raise PermissionDenied()

        payload = json.loads(request.body)
        for team in payload:
            team_id = team["team_id"]
            usernames = team["usernames"]
            members = TournamentMember.objects.filter(
                peloton_profile__username__in=usernames
            )
            if team_id == "unassigned":
                members.update(team=None)
            else:
                team = TournamentTeam.objects.get(pk=team_id)
                members.update(team=team)
        return HttpResponse(status=200)


class UpdatePermissionsView(LoginRequiredMixin, generic.View):
    def post(self, request, uid):
        tournament = get_object_or_404(Tournament, uid=uid)
        if request.user.profile not in tournament.admins.all():
            raise PermissionDenied()

        payload = json.loads(request.body)
        for item in payload:
            TournamentMember.objects.filter(id=item["tournament_member_id"]).update(
                role=item["role"]
            )

        return HttpResponse(status=200)


class RideFiltersView(LoginRequiredMixin, generic.View):
    def get(self, request, uid):
        client = _get_client(request)
        resp = client.get_json(
            "/api/ride/filters",
            headers={"Peloton-Platform": "web"},
            params={"library_type": "on_demand", "browse_category": "cycling"},
        )
        return JsonResponse(resp, status=200)


class EditRidesView(LoginRequiredMixin, generic.View):
    def get(self, request, uid):
        client = _get_client(request)
        instructor_id = request.GET.get("instructor_id") or None
        duration = request.GET.get("duration") or None
        resp = client.search_rides(
            limit=50,
            instructor_id=instructor_id,
            duration=duration,
        )
        return JsonResponse(resp, status=200)

    def post(self, request, uid):
        tournament = get_object_or_404(Tournament, uid=uid)
        if request.user.profile not in tournament.admins.all():
            raise PermissionDenied()

        payload = json.loads(request.body)
        ride_id = payload.get("ride_id")
        client = _get_client(request)
        ride = Ride.from_peloton_id(ride_id, client=client)
        TournamentRide.objects.create(
            tournament=tournament,
            ride=ride,
        )
        return redirect("tournaments:edit", uid, "rides")

    def delete(self, request, uid):
        tournament = get_object_or_404(Tournament, uid=uid)
        if request.user.profile not in tournament.admins.all():
            raise PermissionDenied()

        ride_id = request.body.decode(request.encoding)
        TournamentRide.objects.filter(
            tournament=tournament,
            ride__id=ride_id,
        ).delete()
        return HttpResponse(status=204)


class LinkProfileView(LoginRequiredMixin, generic.View):
    def get(self, request):
        return render(request, "tournaments/authorize.html")

    def post(self, request):
        # First, attempt to login with the Peloton credentials
        username_or_email = request.POST["username_or_email"]
        client = PelotonClient(username=username_or_email)
        try:
            login_resp = client.login(password=request.POST["password"])
        except BadCredentials:
            return self._handle_error(request, f"Invalid Peloton credentials")

        # If the user supplied valid credentials, associate the peloton profile
        # with the currently-logged-in user
        userinfo = client.get_json("/api/me")
        profile = PelotonProfile.from_peloton_id_or_username(
            peloton_id=login_resp["user_id"],
            username=userinfo["username"],
            client=client,
        )
        profile.user = request.user
        profile.peloton_session_id = login_resp["session_id"]
        profile.last_linked = datetime.utcnow()
        profile.save()

        # Redirect to the tournaments page
        return redirect("tournaments:index")

    @staticmethod
    def _handle_error(request, error_message: str):
        return render(
            request,
            "tournaments/authorize.html",
            {"error_message": error_message},
        )


def _get_client(request) -> PelotonClient:
    profile = request.user.profile
    client = PelotonClient()
    client.load_session(profile.peloton_session_id)
    return client
