"""Seed PointTable with the Long Jump rows already used by the old calculator (T61-T64)."""
from django.db import migrations

A = 1200
ROWS = {
    "T61": {"men": (5.541375, 1.012864), "women": (5.796262, 1.297211)},
    "T62": {"men": (5.541375, 0.988727), "women": (5.796262, 1.118046)},
    "T63": {"men": (5.541375, 0.960706), "women": (5.796262, 1.445337)},
    "T64": {"men": (5.541375, 0.904433), "women": (5.796262, 1.181861)},
}


def seed(apps, schema_editor):
    PointTable = apps.get_model("pages", "PointTable")
    for cls, genders in ROWS.items():
        for gender, (b, c) in genders.items():
            PointTable.objects.get_or_create(
                kind="field", event="long jump", classification=cls, gender=gender,
                defaults={"a": A, "b": b, "c": c},
            )


class Migration(migrations.Migration):
    dependencies = [("pages", "0012_roles_judge_pointtable")]
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
