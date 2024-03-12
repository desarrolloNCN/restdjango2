# Generated by Django 5.0 on 2024-03-12 19:48

import django.db.models.deletion
import restapi.models
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Files",
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
                ("filename", models.TextField(max_length=100)),
                ("typeFile", models.TextField(max_length=50)),
            ],
        ),
        migrations.CreateModel(
            name="PlotData",
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
                (
                    "image_path",
                    models.ImageField(
                        blank=True, null=True, upload_to="seismic_plots/"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Proyecto",
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
                ("fecha_creacion", models.DateTimeField(auto_now_add=True)),
                ("uuid", models.UUIDField(default=uuid.uuid4, editable=False)),
            ],
        ),
        migrations.CreateModel(
            name="RegisterUser",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("username", models.TextField()),
                ("email", models.TextField()),
            ],
        ),
        migrations.CreateModel(
            name="SeismicData",
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
                ("data", models.JSONField()),
                ("inv", models.JSONField()),
            ],
        ),
        migrations.CreateModel(
            name="TraceData",
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
                ("formato", models.TextField(blank=True, null=True)),
                ("trace_a_unit", models.TextField(blank=True, null=True)),
                ("traces_a", models.JSONField()),
                ("peak_a", models.TextField(blank=True, null=True)),
                ("trace_v_unit", models.TextField(blank=True, null=True)),
                ("traces_v", models.JSONField()),
                ("peak_v", models.TextField(blank=True, null=True)),
                ("trace_d_unit", models.TextField(blank=True, null=True)),
                ("traces_d", models.JSONField()),
                ("peak_d", models.TextField(blank=True, null=True)),
                ("tiempo_a", models.JSONField()),
            ],
        ),
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
                ("peak_a", models.TextField(blank=True, null=True)),
                ("traces_v", models.JSONField()),
                ("peak_v", models.TextField(blank=True, null=True)),
                ("traces_d", models.JSONField()),
                ("peak_d", models.TextField(blank=True, null=True)),
                ("tiempo_a", models.JSONField()),
            ],
        ),
        migrations.CreateModel(
            name="TraceFilterline",
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
                ("peak_a", models.TextField(blank=True, null=True)),
                ("traces_v", models.JSONField()),
                ("peak_v", models.TextField(blank=True, null=True)),
                ("traces_d", models.JSONField()),
                ("peak_d", models.TextField(blank=True, null=True)),
                ("tiempo_a", models.JSONField()),
            ],
        ),
        migrations.CreateModel(
            name="Traces",
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
            ],
        ),
        migrations.CreateModel(
            name="TraceTrimline",
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
                ("peak_a", models.TextField(blank=True, null=True)),
                ("traces_v", models.JSONField()),
                ("peak_v", models.TextField(blank=True, null=True)),
                ("traces_d", models.JSONField()),
                ("peak_d", models.TextField(blank=True, null=True)),
                ("tiempo_a", models.JSONField()),
            ],
        ),
        migrations.CreateModel(
            name="UploadFile",
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
                ("file", models.FileField(blank=True, null=True, upload_to="uploads/")),
                ("string_data", models.TextField(blank=True, null=True)),
            ],
        ),
        migrations.CreateModel(
            name="FileInfo",
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
                ("nrNetwork", models.IntegerField(blank=True, null=True)),
                ("nrStations", models.IntegerField(blank=True, null=True)),
                ("unit", models.TextField(blank=True, null=True)),
                ("sensi", models.FloatField(blank=True, null=True)),
                (
                    "files",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="restapi.files"
                    ),
                ),
            ],
        ),
        migrations.AddField(
            model_name="files",
            name="proyecto",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="restapi.proyecto"
            ),
        ),
        migrations.AddField(
            model_name="proyecto",
            name="user",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE, to="restapi.registeruser"
            ),
        ),
        migrations.CreateModel(
            name="StationInfo",
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
                ("network", models.TextField(blank=True, null=True)),
                ("station", models.TextField(blank=True, null=True)),
                ("location", models.TextField(blank=True, null=True)),
                ("channel", models.TextField(blank=True, null=True)),
                ("start_time", models.DateField(blank=True, null=True)),
                ("end_time", models.DateField(blank=True, null=True)),
                ("sampling_rate", models.IntegerField(blank=True, null=True)),
                ("delta", models.FloatField(blank=True, null=True)),
                ("npts", models.IntegerField(blank=True, null=True)),
                ("calib", models.FloatField(blank=True, null=True)),
                ("format", models.TextField(blank=True, null=True)),
                (
                    "fileInfo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="restapi.fileinfo",
                    ),
                ),
                (
                    "trace",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE, to="restapi.traces"
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="UploadFileUser",
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
                (
                    "file",
                    models.FileField(
                        blank=True,
                        null=True,
                        upload_to=restapi.models.user_directory_path,
                    ),
                ),
                ("string_data", models.TextField(blank=True, null=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="CalibTraces",
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
                ("stream", models.JSONField()),
                (
                    "iduser",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "idurlFile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="restapi.uploadfileuser",
                    ),
                ),
            ],
        ),
    ]
