from django.db import models
import uuid

from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.core.validators import MaxLengthValidator
# Create your models here.

# @receiver(post_save, sender=settings.AUTH_USER_MODEL)
# def create_auth_token(sender, instance=None, created=False, **kwargs):
#     if created:
#         Token.objects.create(user=instance)

def user_directory_path(instance, filename):
    return f'uploads_user/{instance.user.id}/{filename}'

def user_project_directory_path(instance, filename):
    return f'uploads_user/{instance.user.id}/proyectos/{instance.proyecto.id}/{filename}'

def user_project_img_directory_path(instance, filename):
    return f'uploads_user/{instance.user.id}/proyectos/{instance.id}/img/{filename}'


class SeismicData(models.Model):
    data = models.JSONField()
    inv = models.JSONField()

class UploadFile(models.Model):
    file = models.FileField(upload_to='uploads/', null=True, blank=True)
    string_data = models.TextField(null=True, blank=True)
    ip = models.TextField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

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


# --------------------------------------------------------------

class UploadFileUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    file = models.FileField(upload_to=user_directory_path, null=True, blank=True)
    string_data = models.TextField(null=True, blank=True)

class CalibTraces(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    network  = models.TextField(null=True, blank=True)
    station  = models.TextField(null=True, blank=True)
    location = models.TextField(null=True, blank=True)
    channel  = models.TextField(null=True, blank=True)
    calib    = models.FloatField(null=True, blank=True)
    units    = models.TextField(null=True, blank=True)
# --------------------------------------------------------------

class Proyecto(models.Model):
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    uuid = models.UUIDField(default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.TextField(null=True, blank=True, validators=[MaxLengthValidator(100)])
    desp = models.TextField(null=True, blank=True, validators=[MaxLengthValidator(250)])
    tab = models.JSONField(null=True, blank=True)
    img = models.FileField(upload_to=user_project_img_directory_path, null=True, blank=True)

class ProyectoFiles(models.Model):
    proyecto = models.ForeignKey(Proyecto, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    string_data = models.TextField(null=True, blank=True)
    file = models.FileField(upload_to=user_project_directory_path, null=True, blank=True)
    filename = models.TextField(null=True, blank=True, validators=[MaxLengthValidator(150)])
    unit = models.TextField(null=True, blank=True, validators=[MaxLengthValidator(10)])
    status = models.TextField(null=True, blank=True, validators=[MaxLengthValidator(15)])
    url_gen = models.TextField(null=True, blank=True)
    extra = models.JSONField(null=True, blank=True)
# --------------------------------------------------------------

class PayUser(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    payed = models.BooleanField(default=0)
# --------------------------------------------------------------

class FileInfo(models.Model):
    nrNetwork = models.IntegerField(null=True, blank=True)
    nrStations = models.IntegerField(null=True, blank=True)
    unit = models.TextField(null=True, blank=True)
    sensi = models.FloatField(null=True, blank=True)
    files = models.ForeignKey(ProyectoFiles, on_delete=models.CASCADE)

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

