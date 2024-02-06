# Generated by Django 5.0 on 2024-02-06 16:45

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("restapi", "0003_alter_tracedata_peak_a_alter_tracedata_peak_d_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="tracedatabaseline",
            name="peak_a",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tracedatabaseline",
            name="peak_d",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tracedatabaseline",
            name="peak_v",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tracefilterline",
            name="peak_a",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tracefilterline",
            name="peak_d",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tracefilterline",
            name="peak_v",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tracetrimline",
            name="peak_a",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tracetrimline",
            name="peak_d",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tracetrimline",
            name="peak_v",
            field=models.TextField(blank=True, null=True),
        ),
    ]