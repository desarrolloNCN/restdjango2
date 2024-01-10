# Generated by Django 5.0 on 2024-01-09 23:03

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("restapi", "0007_tracedata_traces_d"),
    ]

    operations = [
        migrations.CreateModel(
            name="TraceDataBaseline",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("traces_a", models.JSONField()),
                ("traces_v", models.JSONField()),
                ("traces_d", models.JSONField()),
                ("tiempo_a", models.JSONField()),
            ],
        ),
    ]
