# Generated by Django 5.0 on 2024-01-08 21:51

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("restapi", "0006_rename_tiempo_tracedata_tiempo_a_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="tracedata",
            name="traces_d",
            field=models.JSONField(default={}),
            preserve_default=False,
        ),
    ]
