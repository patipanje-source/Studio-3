"""python manage.py import_athletes Athlests.member.csv
Columns: country,id,firstName,lastName,gender,dateOfBirth,classification,imgProfile,email   (id = bib number)
Safe to run twice: rows are matched on bib (update_or_create)."""
import csv
from django.core.management.base import BaseCommand, CommandError
from pages.models import Athlete


class Command(BaseCommand):
    help = "Load athletes from a CSV file"

    def add_arguments(self, parser):
        parser.add_argument('path')

    def handle(self, *args, path, **opts):
        created = updated = 0
        seen = {}
        try:
            f = open(path, newline='', encoding='utf-8-sig')
        except OSError as exc:
            raise CommandError(exc)
        with f:
            for line, row in enumerate(csv.DictReader(f), start=2):
                bib = int(row['id'])
                if bib in seen:
                    self.stdout.write(self.style.WARNING(
                        f"Line {line}: ID {bib} ({row['firstName']} {row['lastName']}) is already used by line "
                        f"{seen[bib]} - SKIPPED. Give this athlete a unique ID in the CSV."))
                    continue
                seen[bib] = line
                _, was_new = Athlete.objects.update_or_create(
                    bib=bib,
                    defaults=dict(
                        country=row['country'].strip().upper(),
                        firstName=row['firstName'].strip(),
                        lastName=row['lastName'].strip().upper(),
                        gender=(row.get('gender') or '').strip() or None,
                        dateOfBirth=(row.get('dateOfBirth') or '').strip() or None,
                        classification=(row.get('classification') or '').strip().upper() or None,
                        imgProfile=(row.get('imgProfile') or '').strip(),
                        email=(row.get('email') or '').strip().lower() or None,
                    ),
                )
                created += was_new
                updated += not was_new
        self.stdout.write(self.style.SUCCESS(f"Athletes: {created} created, {updated} updated"))
