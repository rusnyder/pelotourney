from django.test import TestCase
from django.utils import timezone

from tournaments.models import Participant, PelotonProfile, Tournament, TournamentTeam


# Create your tests here.
class TournamentTests(TestCase):
    def test_main_flow(self):
        tournament = Tournament.objects.create(
            name="Test Tournament",
            start_date=timezone.now(),
            end_date=timezone.now(),
        )

        p1 = PelotonProfile.objects.create(id="0001", username="russ")
        p2 = PelotonProfile.objects.create(id="0002", username="ann")
        p3 = PelotonProfile.objects.create(id="0003", username="vic")
        p4 = PelotonProfile.objects.create(id="0004", username="kelly")

        t1 = TournamentTeam.objects.create(name="Best Team", tournament=tournament)
        t2 = TournamentTeam.objects.create(name="Wurst Team", tournament=tournament)

        Participant.objects.create(tournament=tournament, team=t1, peloton_profile=p1)
        Participant.objects.create(tournament=tournament, team=t1, peloton_profile=p2)
        Participant.objects.create(tournament=tournament, team=t2, peloton_profile=p3)
        Participant.objects.create(tournament=tournament, team=t2, peloton_profile=p4)

        self.assertIsNotNone(tournament.participants)
