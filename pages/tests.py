from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Athlete, Attempt, Event, ParticipatingAthlete, Profile, Result, Sport
from .scoring import calculate_event

User = get_user_model()


def make_user(name, role='visitor', staff=False):
    u = User.objects.create_user(username=name, password='test-password-123', is_staff=staff)
    Profile.objects.create(user=u, role=role)
    return u


def make_event(judge=None, number=1, name="Men's Long Jump", gender='M'):
    sport, _ = Sport.objects.get_or_create(sport_code='ATH', defaults={'sport_type': 'Athletics'})
    return Event.objects.create(
        number=number, name=name, classification='T64', date_time=timezone.now() + timedelta(days=1),
        gender=gender, status='Scheduled', location='100.5,13.7', sport=sport, score_format='distance', judge=judge)


def make_athlete(bib, country, cls='T64', gender='Men'):
    return Athlete.objects.create(country=country, bib=bib, firstName=f'A{bib}', lastName=f'L{bib}',
                                  gender=gender, classification=cls, imgProfile='')


class PublicAccessTests(TestCase):  # REQ 1 + 6: guests see results and medals
    def test_guest_sees_home_medal_table(self):
        r = self.client.get(reverse('home'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Medal table')

    def test_guest_can_open_public_pages(self):
        event = make_event()
        for url in (reverse('events'), reverse('all_athletes'), reverse('results'),
                    reverse('result_detail', args=[event.number])):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_management_is_admin_only(self):
        self.assertEqual(self.client.get('/manage/').status_code, 302)
        self.client.force_login(make_user('j', 'judge'))
        self.assertEqual(self.client.get('/manage/').status_code, 302)
        self.client.force_login(make_user('boss', staff=True))
        self.assertEqual(self.client.get('/manage/events/').status_code, 200)


class RegisterTests(TestCase):  # REQ 1
    def test_register_each_role(self):
        for role in ('agent', 'sporter', 'judge', 'visitor'):
            self.client.logout()
            r = self.client.post('/register/', {'uid': f'user_{role}', 'pwd1': 'longenough1', 'pwd2': 'longenough1',
                                               'email': f'{role}@x.com', 'role': role})
            self.assertEqual(r.status_code, 302)
            self.assertEqual(User.objects.get(username=f'user_{role}').profile.role, role)

    def test_cannot_self_register_as_admin(self):
        self.client.post('/register/', {'uid': 'sneaky', 'pwd1': 'longenough1', 'pwd2': 'longenough1',
                                       'email': 's@x.com', 'role': 'admin'})
        self.assertFalse(User.objects.filter(username='sneaky').exists())

    def test_sporter_is_linked_to_athlete_by_email(self):
        a = make_athlete(500, 'THA'); a.email = 'me@x.com'; a.save()
        self.client.post('/register/', {'uid': 'runner', 'pwd1': 'longenough1', 'pwd2': 'longenough1',
                                       'email': 'ME@x.com', 'role': 'sporter'})
        self.assertEqual(User.objects.get(username='runner').profile.athlete_id, a.id)


class ResultPermissionTests(TestCase):  # REQ 3 + 4
    def setUp(self):
        self.judge = make_user('judge1', 'judge')
        self.other = make_user('judge2', 'judge')
        self.event = make_event(judge=self.judge)
        self.url = reverse('result_detail', args=[self.event.number])
        self.a = make_athlete(1, 'THA')
        ParticipatingAthlete.objects.create(event=self.event, athlete=self.a)

    def test_guest_and_wrong_judge_cannot_edit(self):
        data = {'mode': 'manual', f'point-{self.a.id}': 900, f'rank-{self.a.id}': 1, f'medal-{self.a.id}': 1}
        self.assertEqual(self.client.post(self.url, data).status_code, 403)
        self.client.force_login(self.other)
        self.assertEqual(self.client.post(self.url, data).status_code, 403)
        self.assertFalse(Result.objects.exists())

    def test_assigned_judge_and_admin_can_edit(self):
        data = {'mode': 'manual', f'point-{self.a.id}': 900, f'rank-{self.a.id}': 1, f'medal-{self.a.id}': 1}
        self.client.force_login(self.judge)
        self.assertEqual(self.client.post(self.url, data).status_code, 302)
        self.assertEqual(Result.objects.get().point, 900)
        self.client.force_login(make_user('boss', staff=True))
        data[f'point-{self.a.id}'] = 910
        self.client.post(self.url, data)
        self.assertEqual(Result.objects.get().point, 910)

    def test_event_without_judge_is_admin_only(self):
        event = make_event(number=2)  # no judge
        self.client.force_login(self.judge)
        r = self.client.post(reverse('result_detail', args=[2]), {'mode': 'manual'})
        self.assertEqual(r.status_code, 403)


class PointsCalculationTests(TestCase):  # REQ 5: ranking by POINTS, medals automatic
    def setUp(self):
        self.event = make_event()
        self.admin = make_user('boss', staff=True)

    def _post_scores(self, scores):
        """scores: {athlete: metres}; one 'score' attempt each"""
        data = {'mode': 'calculate'}
        for a, metres in scores.items():
            ParticipatingAthlete.objects.get_or_create(event=self.event, athlete=a)
        for a, metres in scores.items():
            for n in range(1, 7):
                data[f'status-{a.id}-{n}'] = 'score' if n == 1 else 'unset'
                data[f'value-{a.id}-{n}'] = str(metres) if n == 1 else ''
        self.client.force_login(self.admin)
        return self.client.post(reverse('result_detail', args=[self.event.number]), data)

    def test_points_not_raw_score_decide_rank(self):
        # T62 athletes need a longer jump than T64 for the same points, so the SHORTER raw jump can win
        t62 = make_athlete(1, 'THA', 'T62')
        t64 = make_athlete(2, 'JPN', 'T64')
        self._post_scores({t62: 5.50, t64: 5.60})
        r62, r64 = Result.objects.get(athlete=t62), Result.objects.get(athlete=t64)
        # the T62 jumper jumped 10 cm SHORTER but scores more points, so ranks first and gets gold
        self.assertGreater(r62.point, r64.point)
        self.assertEqual((r62.rank, r62.medal), (1, 1))
        self.assertEqual((r64.rank, r64.medal), (2, 2))

    def test_foul_only_athlete_gets_no_rank(self):
        a, b = make_athlete(1, 'THA'), make_athlete(2, 'JPN')
        ParticipatingAthlete.objects.create(event=self.event, athlete=a)
        ParticipatingAthlete.objects.create(event=self.event, athlete=b)
        data = {'mode': 'calculate'}
        for ath, st, val in ((a, 'score', '6.1'), (b, 'foul', '')):
            for n in range(1, 7):
                data[f'status-{ath.id}-{n}'] = st if n == 1 else 'unset'
                data[f'value-{ath.id}-{n}'] = val if n == 1 else ''
        self.client.force_login(self.admin)
        self.client.post(reverse('result_detail', args=[self.event.number]), data)
        self.assertEqual(Result.objects.get(athlete=a).medal, 1)
        self.assertEqual((Result.objects.get(athlete=b).rank, Result.objects.get(athlete=b).medal), (0, 0))

    def test_missing_points_row_gives_clear_error(self):
        a = make_athlete(1, 'THA', 'T20')   # no points row for T20
        ParticipatingAthlete.objects.create(event=self.event, athlete=a)
        ok, msg = calculate_event(self.event)
        self.assertFalse(ok); self.assertIn('T20', msg)

    def test_men_gender_word_from_csv_is_understood(self):
        a = make_athlete(1, 'THA', 'T64', gender='Men')
        ParticipatingAthlete.objects.create(event=self.event, athlete=a)
        self.assertTrue(calculate_event(self.event)[0])


class MedalTableTests(TestCase):  # REQ 6
    def test_medal_table_counts_and_orders(self):
        event = make_event()
        for bib, country, medal in ((1, 'THA', 1), (2, 'JPN', 2), (3, 'THA', 3)):
            a = make_athlete(bib, country)
            Result.objects.create(event=event, athlete=a, medal=medal, rank=medal, point=100 * (4 - medal))
        r = self.client.get(reverse('home'))
        table = r.context['table']
        self.assertEqual([row['country'] for row in table], ['THA', 'JPN'])
        self.assertEqual((table[0]['gold'], table[0]['bronze'], table[0]['total']), (1, 1, 2))
        self.assertEqual(r.context['totals']['total'], 3)

    def test_athlete_directory_hides_emails_from_guests(self):
        a = make_athlete(1, 'THA'); a.email = 'secret@x.com'; a.save()
        self.assertNotContains(self.client.get(reverse('all_athletes')), 'secret@x.com')


class ImportTests(TestCase):
    def test_duplicate_ids_in_csv_are_skipped_not_overwritten(self):
        import tempfile, os
        from io import StringIO
        from django.core.management import call_command
        csv_text = ("country,id,firstName,lastName,gender,dateOfBirth,classification,imgProfile,email\n"
                    "THA,805,Anna,ONE,Men,,T64,,\nTHA,805,Bob,TWO,Men,,T64,,\n")
        with tempfile.NamedTemporaryFile('w', suffix='.csv', delete=False) as f:
            f.write(csv_text)
        out = StringIO()
        call_command('import_athletes', f.name, stdout=out)
        os.unlink(f.name)
        self.assertEqual(Athlete.objects.get(bib=805).firstName, 'Anna')
        self.assertIn('SKIPPED', out.getvalue())
