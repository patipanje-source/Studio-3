"""python manage.py import_points data/points.csv
Columns: kind,event,classification,gender,a,b,c   (kind = field|track, gender = men|women, event = e.g. 'long jump')
This is the ERD's FIELDPOINT / TRACKPOINT data. Take the numbers from the official points table your course gives you."""
import csv
from django.core.management.base import BaseCommand, CommandError
from pages.models import PointTable


class Command(BaseCommand):
    help = "Load points-formula parameters from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument('path')

    def handle(self, *args, path, **opts):
        n = 0
        try:
            f = open(path, newline='', encoding='utf-8-sig')
        except OSError as exc:
            raise CommandError(exc)
        with f:
            for row in csv.DictReader(f):
                PointTable.objects.update_or_create(
                    kind=row['kind'].strip().lower(), event=row['event'].strip().lower(),
                    classification=row['classification'].strip().upper(), gender=row['gender'].strip().lower(),
                    defaults=dict(a=float(row['a']), b=float(row['b']), c=float(row['c'])))
                n += 1
        self.stdout.write(self.style.SUCCESS(f"Point-table rows loaded: {n}"))
