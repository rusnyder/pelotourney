from datetime import datetime, timedelta

from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render, reverse
from django.views import generic

from .external.peloton import BadCredentials, NotAuthenticated, PelotonClient
from .models import PelotonProfile, Tournament, Workout


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


class DetailView(generic.View):
    def get(self, request, pk):
        tournament = get_object_or_404(Tournament, pk=pk)
        if not (
            tournament.visibility == Tournament.Visibility.PUBLIC
            or request.user.is_authenticated
        ):
            raise PermissionDenied()
        context = {"tournament": tournament}
        return render(request, "tournaments/detail.html", context)


class SyncView(LoginRequiredMixin, generic.View):
    def post(self, request, pk):
        # Ensure the tournament exists
        tournament = get_object_or_404(Tournament, pk=pk)

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
                end_date=tournament.end_date,
                ride_ids=tournament.rides.values_list("peloton_id", flat=True),
            )
            for workout_data in workouts:
                Workout.from_peloton_id(workout_data["id"], client)

        # Redirect back to the tournament page
        tournament.last_synced = datetime.utcnow()
        tournament.save()
        return HttpResponseRedirect(reverse("tournaments:detail", args=[tournament.id]))


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
        return HttpResponseRedirect(reverse("tournaments:index"))

    @staticmethod
    def _handle_error(request, error_message: str):
        return render(
            request,
            "tournaments/authorize.html",
            {"error_message": error_message},
        )
