from abc import abstractmethod
from datetime import datetime
from functools import reduce
from operator import ior
from typing import TypeVar

import nanoid
from django.contrib.auth.models import User
from django.db import models
from django.db.models import F, Q, QuerySet, Subquery, Sum, Window
from django.db.models.functions import FirstValue
from django.utils.translation import gettext_lazy as _
from fernet_fields import EncryptedTextField

from .external.peloton import NotAuthenticated, PelotonClient

PelotonModelType = TypeVar("PelotonModelType", bound="PelotonModel")


def random_uid():
    """
    Wrapper around nanoid that pins the number of characters generated
    to protect against upstream changes.
    """
    return nanoid.generate(size=21)


class BaseModel(models.Model):
    id = models.BigAutoField(primary_key=True)
    uid = models.CharField(
        max_length=32,
        null=False,
        blank=False,
        unique=True,
        editable=False,
        default=random_uid,
    )

    class Meta:
        abstract = True


class PelotonModel(BaseModel):
    peloton_id = models.CharField(max_length=64, unique=True)
    raw = models.JSONField(null=True)

    @abstractmethod
    def update_from_api(self, client: PelotonClient) -> None:
        raise NotImplementedError

    @classmethod
    def from_peloton_id(
        cls, peloton_id: str, client: PelotonClient
    ) -> PelotonModelType:
        # Return existing model if it exists and cannot be changed
        model = cls.objects.filter(peloton_id=peloton_id).first()
        if model and model.is_finalized():
            return model

        # Create a model class if we don't have one yet
        if not model:
            model = cls(peloton_id=peloton_id)  # type: PelotonModelType

        # Merge in fields from the Peloton API
        model.update_from_api(client=client)
        model.save()
        return model

    def is_finalized(self) -> bool:
        """Indicates whether an object is immutable or if it can be updated from Peloton API data.

        This defaults to `True`, meaning the data cannot be modified.

        Child classes can override this to inspect the model and make more dynamic
        decisions about whether a model can be updated (e.g. - if a `status` field is not `COMPLETE`, etc.)
        """
        return True

    class Meta:
        abstract = True


class PelotonProfile(PelotonModel):
    # Allow peloton_id to be nullable so users can be persisted by their
    # username alone, and looked up later
    peloton_id = models.CharField(max_length=64, unique=True, null=True)
    username = models.CharField(max_length=150, unique=True)
    peloton_session_id = EncryptedTextField(null=True)
    image_url = models.URLField(null=True)
    user = models.OneToOneField(
        User, null=True, on_delete=models.DO_NOTHING, related_name="profile"
    )
    last_linked = models.DateTimeField(null=True)

    @property
    def best_workouts(self) -> QuerySet:
        """Returns a query set producing the highest-output workout for each ride."""
        subquery = (
            Workout.objects.filter(peloton_profile=self)
            .annotate(
                best_pk=Window(
                    expression=FirstValue("pk"),
                    partition_by=[F("ride__id")],
                    order_by=F("total_work").desc(),
                )
            )
            .values("best_pk")
        )
        return Workout.objects.filter(pk__in=Subquery(subquery))

    @classmethod
    def from_peloton_id_or_username(
        cls, peloton_id: str, username: str, client: PelotonClient
    ) -> "PelotonProfile":
        # Return existing model if it exists and cannot be changed
        filter_fields = {}
        if peloton_id:
            filter_fields["peloton_id"] = peloton_id
        if username:
            filter_fields["username"] = username

        # Bitwise OR the filters together
        filters = reduce(ior, [Q(**{k: v}) for k, v in filter_fields.items()])
        model = cls.objects.filter(filters).first()
        if model and model.is_finalized():
            return model

        # Create a model class if we don't have one yet
        if not model:
            model = cls(**filter_fields)  # type: PelotonModelType

        # Merge in fields from the Peloton API
        model.update_from_api(client=client)
        model.save()
        return model

    def update_from_api(self, client: PelotonClient) -> None:
        if self.peloton_id:
            data = client.get_json(f"/api/user/{self.peloton_id}")
            self.username = self.username = data["username"]
        elif self.username:
            data = client.get_json(f"/api/user/{self.username}")
            self.peloton_id = data["id"]
        else:
            raise ValueError("Unable to lookup user without peloton_id or username")
        self.image_url = data["image_url"]
        self.raw = data

    def is_finalized(self) -> bool:
        return bool(self.image_url)

    def has_valid_session(self) -> bool:
        if not self.peloton_session_id:
            return False
        client = PelotonClient()
        try:
            client.load_session(str(self.peloton_session_id))
            return True
        except NotAuthenticated:
            return False

    def __str__(self):
        return self.username


class Instructor(PelotonModel):
    name = models.CharField(max_length=150)
    image_url = models.CharField(max_length=150)

    def update_from_api(self, client: PelotonClient) -> None:
        data = client.get_json(f"/api/instructor/{self.peloton_id}")
        self.name = data["name"]
        self.image_url = data["image_url"]
        self.raw = data

    def is_finalized(self) -> bool:
        return bool(self.name)

    def __str__(self):
        return self.name


class Ride(PelotonModel):
    title = models.TextField(null=True)
    description = models.TextField(null=True)
    image_url = models.URLField(null=True)
    scheduled_start_time = models.DateTimeField(null=True)
    instructor = models.ForeignKey(Instructor, null=True, on_delete=models.CASCADE)

    def update_from_api(self, client: PelotonClient) -> None:
        data = client.get_json(f"/api/ride/{self.peloton_id}")
        self.title = data["title"]
        self.description = data["description"]
        self.image_url = data["image_url"]
        self.scheduled_start_time = datetime.utcfromtimestamp(
            data["scheduled_start_time"]
        )
        self.instructor = Instructor.from_peloton_id(data["instructor_id"], client)
        self.raw = data

    def is_finalized(self) -> bool:
        return bool(self.title)

    def __str__(self):
        value = self.title or self.peloton_id
        if self.instructor:
            value += f" ({self.instructor.name})"
        return str(value)


class Workout(PelotonModel):
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE)
    peloton_profile = models.ForeignKey(
        PelotonProfile, on_delete=models.CASCADE, related_name="workouts"
    )
    status = models.CharField(max_length=32)  # e.g. - COMPLETE
    start_time = models.DateTimeField(null=True)
    end_time = models.DateTimeField(null=True)
    total_work = models.FloatField(
        null=True
    )  # KJs (divide by 1000 to get recognizable value)

    @property
    def duration(self) -> float:
        """Returns the duration of the workout in seconds (or 0 if not yet completed)"""
        if self.raw.get("start_time") and self.raw.get("end_time"):
            return self.raw["end_time"] - self.raw["start_time"]
        else:
            return 0

    @property
    def average_output(self) -> float:
        duration = self.duration
        if duration <= 0:
            return 0
        else:
            return self.total_work / duration

    def update_from_api(self, client: PelotonClient) -> None:
        data = client.get_json(f"/api/workout/{self.peloton_id}")
        ride = Ride.from_peloton_id(data["ride"]["id"], client)
        profile = PelotonProfile.from_peloton_id(data["user_id"], client)
        self.ride = ride
        self.peloton_profile = profile
        self.status = data["status"]
        self.total_work = data.get("total_work")
        if data.get("start_time"):
            self.start_time = datetime.utcfromtimestamp(data["start_time"])
        if data.get("end_time"):
            self.end_time = datetime.utcfromtimestamp(data["end_time"])
        self.raw = data

    def is_finalized(self) -> bool:
        return self.status and self.status == "COMPLETED"

    def __str__(self):
        return (
            f"{self.ride.title} "
            f"("
            f"Rider: {self.peloton_profile.username}, "
            f"Total Output: {int(self.total_work / 1000)} kj"
            f")"
        )


class Tournament(BaseModel):
    class Format(models.TextChoices):
        SIMPLE = "simple", _("Simple")

    class Visibility(models.TextChoices):
        PUBLIC = "public", _("Public")
        PRIVATE = "privte", _("Private")

    name = models.CharField(max_length=200)
    format = models.CharField(max_length=64, default=Format.SIMPLE)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    last_synced = models.DateTimeField(null=True)
    visibility = models.CharField(max_length=16, default=Visibility.PRIVATE)

    participants = models.ManyToManyField(PelotonProfile, through="TournamentMember")
    rides = models.ManyToManyField(Ride, through="TournamentRide")

    @property
    def admins(self) -> QuerySet:
        return PelotonProfile.objects.filter(
            tournamentmember__tournament=self,
            tournamentmember__role__in={
                TournamentMember.Role.OWNER,
                TournamentMember.Role.MANAGER,
            },
        )

    @property
    def unassigned(self) -> QuerySet:
        return PelotonProfile.objects.filter(
            tournamentmember__tournament=self,
            tournamentmember__team__isnull=True,
        )

    def roles(self):
        return TournamentMember.Role.choices

    def __str__(self):
        return self.name


class TournamentTeam(BaseModel):
    name = models.CharField(max_length=200)
    tournament = models.ForeignKey(
        Tournament, on_delete=models.CASCADE, related_name="teams"
    )
    members = models.ManyToManyField(PelotonProfile, through="TournamentMember")

    @property
    def best_workouts(self) -> QuerySet:
        """Returns the best ride for each rider for this tournament"""
        subquery = self._best_workouts_filter(returns="pk").values("pk")
        return Workout.objects.filter(pk__in=Subquery(subquery))

    @property
    def total_work(self) -> float:
        """Returns the sum of outputs the best ride for each rider for this tournament"""
        return (
            self._best_workouts_filter(returns="total_work").aggregate(
                sum=Sum("total_work")
            )["sum"]
            or 0
        )

    def _best_workouts_filter(self, returns: str) -> QuerySet:
        return Workout.objects.filter(
            peloton_profile__tournamentteam=self, ride__tournament=self.tournament
        ).annotate(
            best_pk=Window(
                expression=FirstValue(returns),
                partition_by=[F("ride__id"), F("peloton_profile__id")],
                order_by=F("total_work").desc(),
            )
        )

    def __str__(self):
        return self.name


class TournamentRide(BaseModel):
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    ride = models.ForeignKey(Ride, on_delete=models.CASCADE)


class TournamentMember(BaseModel):
    class Role(models.TextChoices):
        OWNER = "owner", _("Owner")
        MANAGER = "manager", _("Manager")
        MEMBER = "member", _("Member")

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE)
    peloton_profile = models.ForeignKey(PelotonProfile, on_delete=models.CASCADE)
    team = models.ForeignKey(TournamentTeam, on_delete=models.SET_NULL, null=True)
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MEMBER)

    class Meta:
        unique_together = [["tournament", "peloton_profile", "team"]]

    def __str__(self):
        team_name = self.team.name if self.team else "unassigned"
        return f"{self.peloton_profile.username} ({team_name})"
