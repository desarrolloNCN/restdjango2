# Generated by Django 5.0 on 2024-03-30 00:42

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("restapi", "0010_proyectofiles_filename"),
    ]

    operations = [
        migrations.AddField(
            model_name="calibtraces",
            name="units",
            field=models.TextField(blank=True, null=True),
        ),
    ]
