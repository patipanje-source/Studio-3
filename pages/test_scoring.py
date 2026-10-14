from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Athlete, Attempt, Event, ParticipatingAthlete, Result, Sport


class MedalCalculatorTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username="judge",
            password="judge-password-123",
            is_staff=True,
        )
        self.client.force_login(staff)
        self.sport = Sport.objects.create(sport_type="Para Athletics", sport_code="PA")
        self.event = Event.objects.create(
            number=7,
            name="Long Jump T61-T64 Open",
            classification="T61-T64",
            date_time=timezone.now(),
            gender="M",
            status="Scheduled",
            location="Test venue",
            sport=self.sport,
        )

    def add_athlete(self, bib, sport_class):
        athlete = Athlete.objects.create(
            country="USA",
            bib=bib,
            firstName=f"Athlete{bib}",
            lastName="Test",
            gender="M",
            classification=sport_class,
            imgProfile="athletePfp/test.jpg",
        )
        ParticipatingAthlete.objects.create(event=self.event, athlete=athlete)
        return athlete

    def submit_marks(self, marks_by_athlete):
        data = {"event_id": str(self.event.id)}
        for athlete, marks in marks_by_athlete.items():
            for number in range(1, 7):
                mark = marks[number - 1] if number <= len(marks) else None
                data[f"status-{athlete.id}-{number}"] = "score" if mark is not None else "unset"
                data[f"distance-{athlete.id}-{number}"] = str(mark) if mark is not None else ""
        return self.client.post(reverse("medal_calculator"), data)

    def test_staff_can_load_calculator_for_long_jump_event(self):
        self.add_athlete(101, "T61")

        response = self.client.get(reverse("medal_calculator"), {"event": self.event.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Long Jump Medal Calculator")
        self.assertContains(response, "Athlete101 Test")

    def test_points_rank_mixed_classes_and_save_marks_in_centimetres(self):
        t61 = self.add_athlete(101, "T61")
        t64 = self.add_athlete(102, "T64")

        response = self.submit_marks({t61: ["5.50"], t64: ["6.00"]})

        self.assertEqual(response.status_code, 302)
        t61_result = Result.objects.get(event=self.event, athlete=t61)
        t64_result = Result.objects.get(event=self.event, athlete=t64)
        self.assertEqual(t61_result.best_score, 550)
        self.assertEqual(t64_result.best_score, 600)
        self.assertGreater(t61_result.point, t64_result.point)
        self.assertEqual((t61_result.rank, t61_result.medal), (1, 1))
        self.assertEqual((t64_result.rank, t64_result.medal), (2, 2))
        self.assertEqual(Attempt.objects.get(result=t64_result, attempt_number=1).score, 600)

    def test_equal_best_marks_use_second_best_attempt_countback(self):
        shorter_second = self.add_athlete(101, "T61")
        longer_second = self.add_athlete(102, "T61")

        self.submit_marks({shorter_second: ["5.00", "4.00"], longer_second: ["5.00", "4.10"]})

        first_result = Result.objects.get(event=self.event, athlete=shorter_second)
        second_result = Result.objects.get(event=self.event, athlete=longer_second)
        self.assertEqual((second_result.rank, second_result.medal), (1, 1))
        self.assertEqual((first_result.rank, first_result.medal), (2, 2))

    def test_more_than_eight_participants_is_rejected(self):
        for bib in range(101, 110):
            self.add_athlete(bib, "T61")

        response = self.client.post(reverse("medal_calculator"), {"event_id": self.event.id})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "supports up to 8 athletes")
        self.assertFalse(Result.objects.filter(event=self.event).exists())

    def test_non_staff_cannot_use_calculator(self):
        user = get_user_model().objects.create_user(username="member", password="member-password-123")
        self.client.force_login(user)

        response = self.client.get(reverse("medal_calculator"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("home"))
