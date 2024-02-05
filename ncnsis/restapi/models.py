from django.db import models
import uuid

# Create your models here.

class SeismicData(models.Model):
    data = models.JSONField()
    inv = models.JSONField()

class UploadFile(models.Model):
    file = models.FileField(upload_to='uploads/', null=True, blank=True)
    string_data = models.TextField(null=True, blank=True)

class PlotData(models.Model):
    image_path = models.ImageField(upload_to='seismic_plots/', null=True, blank=True)

class TraceData(models.Model):
    traces_a = models.JSONField()
    traces_v = models.JSONField()
    traces_d = models.JSONField()
    tiempo_a = models.JSONField()

class TraceDataBaseline(models.Model):
    traces_a = models.JSONField()
    traces_v = models.JSONField()
    traces_d = models.JSONField()
    tiempo_a = models.JSONField()

class TraceFilterline(models.Model):
    traces_a = models.JSONField()
    traces_v = models.JSONField()
    traces_d = models.JSONField()
    tiempo_a = models.JSONField()

class TraceTrimline(models.Model):
    traces_a = models.JSONField()
    traces_v = models.JSONField()
    traces_d = models.JSONField()
    tiempo_a = models.JSONField()

class Proyecto(models.Model):
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)

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

