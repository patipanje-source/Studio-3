"""Repair the legacy partially-created pages schema without rewriting old migrations."""

from django.db import migrations


def repair_legacy_schema(apps, schema_editor):
    connection = schema_editor.connection
    tables = set(connection.introspection.table_names())
    models_in_dependency_order = (
        "Athlete",
        "Profile",
        "Sport",
        "Event",
        "ParticipatingAthlete",
        "Result",
        "Attempt",
    )

    athlete_model = apps.get_model("pages", "Athlete")
    athlete_table = athlete_model._meta.db_table
    if athlete_table in tables:
        with connection.cursor() as cursor:
            columns = {
                column.name
                for column in connection.introspection.get_table_description(cursor, athlete_table)
            }
        if "athlete_id" in columns and "bib" not in columns:
            quote = connection.ops.quote_name
            schema_editor.execute(
                f"ALTER TABLE {quote(athlete_table)} "
                f"RENAME COLUMN {quote('athlete_id')} TO {quote('bib')}"
            )
            columns.remove("athlete_id")
            columns.add("bib")
        for field_name in ("remark", "phone"):
            field = athlete_model._meta.get_field(field_name)
            if field.column not in columns:
                schema_editor.add_field(athlete_model, field)
                columns.add(field.column)

    for model_name in models_in_dependency_order:
        model = apps.get_model("pages", model_name)
        if model._meta.db_table not in tables:
            schema_editor.create_model(model)
            tables.add(model._meta.db_table)


class Migration(migrations.Migration):
    dependencies = [("pages", "0010_remove_result_remark")]

    operations = [migrations.RunPython(repair_legacy_schema, migrations.RunPython.noop)]
