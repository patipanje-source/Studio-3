"""python manage.py import_events data/events.sample.csv
Columns: number,name,sport_code,sport_name,classification,gender,date_time,status,stage,score_format,longitude,latitude,remark
  gender: M / F      score_format: distance | time | points | sets      date_time: 2026-10-20 10:00
Sports are created when sport_code is new. Safe to run twice (matched on event number)."""
import csv
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from pages.models import Event, Sport


class Command(BaseCommand):
    help = "Load events (the competition schedule) from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument('path')

    def handle(self, *args, path, **opts):
        created = updated = 0
        try:
            f = open(path, newline='', encoding='utf-8-sig')
        except OSError as exc:
            raise CommandError(exc)
        with f:
            for row in csv.DictReader(f):
                sport, _ = Sport.objects.get_or_create(
                    sport_code=row['sport_code'].strip().upper(),
                    defaults={'sport_type': (row.get('sport_name') or row['sport_code']).strip()})
                when = timezone.make_aware(datetime.strptime(row['date_time'].strip(), '%Y-%m-%d %H:%M'))
                lng = (row.get('longitude') or '100.5018').strip()
                lat = (row.get('latitude') or '13.7563').strip()
                _, was_new = Event.objects.update_or_create(
                    number=int(row['number']),
                    defaults=dict(
                        name=row['name'].strip(), sport=sport,
                        classification=(row.get('classification') or '').strip() or None,
                        gender=(row.get('gender') or '').strip() or None,
                        date_time=when, status=(row.get('status') or 'Scheduled').strip(),
                        stage=(row.get('stage') or '').strip() or None,
                        score_format=(row.get('score_format') or '').strip() or None,
                        location=f"{lng},{lat}", remark=(row.get('remark') or '').strip() or None,
                    ),
                )
                created += was_new
                updated += not was_new
        self.stdout.write(self.style.SUCCESS(f"Events: {created} created, {updated} updated"))
