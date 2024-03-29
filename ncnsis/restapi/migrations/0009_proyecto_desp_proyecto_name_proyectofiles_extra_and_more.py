# Generated by Django 5.0 on 2024-03-25 00:29

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("restapi", "0008_rename_userfile_proyectofiles_file_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="proyecto",
            name="desp",
            field=models.TextField(
                blank=True,
                null=True,
                validators=[django.core.validators.MaxLengthValidator(250)],
            ),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="name",
            field=models.TextField(
                blank=True,
                null=True,
                validators=[django.core.validators.MaxLengthValidator(100)],
            ),
        ),
        migrations.AddField(
            model_name="proyectofiles",
            name="extra",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="proyectofiles",
            name="status",
            field=models.TextField(
                blank=True,
                null=True,
                validators=[django.core.validators.MaxLengthValidator(15)],
            ),
        ),
        migrations.AddField(
            model_name="proyectofiles",
            name="unit",
            field=models.TextField(
                blank=True,
                null=True,
                validators=[django.core.validators.MaxLengthValidator(10)],
            ),
        ),
    ]
