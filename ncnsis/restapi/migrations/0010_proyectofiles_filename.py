# Generated by Django 5.0 on 2024-03-25 19:25

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("restapi", "0009_proyecto_desp_proyecto_name_proyectofiles_extra_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyectofiles",
            name="filename",
            field=models.TextField(
                blank=True,
                null=True,
                validators=[django.core.validators.MaxLengthValidator(150)],
            ),
        ),
    ]
