from django.db import models

# Create your models here.

class SeismicData(models.Model):
    data = models.JSONField()

class UploadFile(models.Model):
    file = models.FileField(upload_to='uploads/', null=True, blank=True)
    string_data = models.TextField(null=True, blank=True)

class PlotData(models.Model):
    image_path = models.ImageField(upload_to='seismic_plots/', null=True, blank=True)

class TraceData(models.Model):
    traces = models.JSONField()
    tiempo = models.JSONField()