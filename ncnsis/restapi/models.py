from django.db import models
import uuid

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token

# Create your models here.

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)

class SeismicData(models.Model):
    data = models.JSONField()
    inv = models.JSONField()

class UploadFile(models.Model):
    file = models.FileField(upload_to='uploads/', null=True, blank=True)
    string_data = models.TextField(null=True, blank=True)

class PlotData(models.Model):
    image_path = models.ImageField(upload_to='seismic_plots/', null=True, blank=True)

class TraceData(models.Model):
    formato = models.TextField(null=True, blank=True)

    trace_a_unit = models.TextField(null=True, blank=True)
    traces_a = models.JSONField()
    peak_a = models.TextField(null=True, blank=True)

    trace_v_unit = models.TextField(null=True, blank=True)
    traces_v = models.JSONField()
    peak_v = models.TextField(null=True, blank=True)

    trace_d_unit = models.TextField(null=True, blank=True)
    traces_d = models.JSONField()
    peak_d = models.TextField(null=True, blank=True)

    tiempo_a = models.JSONField()


class TraceDataBaseline(models.Model):
    traces_a = models.JSONField()
    peak_a = models.TextField(null=True, blank=True)
    traces_v = models.JSONField()
    peak_v = models.TextField(null=True, blank=True)
    traces_d = models.JSONField()
    peak_d = models.TextField(null=True, blank=True)
    tiempo_a = models.JSONField()

class TraceFilterline(models.Model):
    traces_a = models.JSONField()
    peak_a = models.TextField(null=True, blank=True)
    traces_v = models.JSONField()
    peak_v = models.TextField(null=True, blank=True)
    traces_d = models.JSONField()
    peak_d = models.TextField(null=True, blank=True)
    tiempo_a = models.JSONField()

class TraceTrimline(models.Model):
    traces_a = models.JSONField()
    peak_a = models.TextField(null=True, blank=True)
    traces_v = models.JSONField()
    peak_v = models.TextField(null=True, blank=True)
    traces_d = models.JSONField()
    peak_d = models.TextField(null=True, blank=True)
    tiempo_a = models.JSONField()

class RegisterUser(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = models.TextField()
    email = models.TextField()

class Proyecto(models.Model):
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    user = models.ForeignKey(RegisterUser, on_delete=models.CASCADE)

class Files(models.Model):
    filename = models.TextField(max_length=100)
    typeFile = models.TextField(max_length=50)
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)

class FileInfo(models.Model):
    nrNetwork = models.IntegerField(null=True, blank=True)
    nrStations = models.IntegerField(null=True, blank=True)
    unit = models.TextField(null=True, blank=True)
    sensi = models.FloatField(null=True, blank=True)
    files = models.ForeignKey(Files, on_delete=models.CASCADE)

class Traces(models.Model):
    traces_a = models.JSONField()
    traces_v = models.JSONField()
    traces_d = models.JSONField()

class StationInfo(models.Model):
    network = models.TextField(null=True, blank=True)
    station = models.TextField(null=True, blank=True)
    location = models.TextField(null=True, blank=True)
    channel = models.TextField(null=True, blank=True)
    start_time = models.DateField(null=True, blank=True)
    end_time = models.DateField(null=True, blank=True)
    sampling_rate = models.IntegerField(null=True, blank=True)
    delta = models.FloatField(null=True, blank=True)
    npts = models.IntegerField(null=True, blank=True)
    calib = models.FloatField(null=True, blank=True)
    format = models.TextField(null=True, blank=True)
    fileInfo = models.ForeignKey(FileInfo, on_delete=models.CASCADE)
    trace = models.OneToOneField(Traces, on_delete=models.CASCADE)

