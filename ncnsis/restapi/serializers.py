from django.contrib.auth.models import Group, User
from rest_framework import serializers

from .models import *


class UserSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = User
        fields = ['url', 'username', 'email', 'groups']


class GroupSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Group
        fields = ['url', 'name']

class SeismicDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = SeismicData
        fields = "__all__"

class FileUploadSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadFile
        fields = ('id', 'file', 'string_data')

class PlotDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlotData
        fields = "__all__"



class TraceDataSerializer(serializers.ModelSerializer):
    class Meta:
        model = TraceData
        fields = "__all__"

class TraceDataBaselineSerializer(serializers.ModelSerializer):
    class Meta:
        model = TraceDataBaseline
        fields = "__all__"

class TraceFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = TraceFilterline
        fields = "__all__"

class TraceTrimSerializer(serializers.ModelSerializer):
    class Meta:
        model = TraceTrimline
        fields = "__all__"



class ProyectoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proyecto
        fields = ['id', 'fecha_creacion', 'uuid']


class FilesSerializer(serializers.ModelSerializer):
    proyecto = ProyectoSerializer() 

    class Meta:
        model = Files
        fields = ['id', 'filename', 'typeFile', 'proyecto']

class FileInfoSerializer(serializers.ModelSerializer):
    files = FilesSerializer()  

    class Meta:
        model = FileInfo
        fields = ['id', 'nrNetwork', 'nrStations', 'unit', 'sensi', 'files']

class TracesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Traces
        fields = "__all__"

class StationInfoSerializer(serializers.ModelSerializer):
    fileInfo = FileInfoSerializer()
    trace = TracesSerializer()

    class Meta:
        model = StationInfo
        fields = ['network','station','location','channel','start_time' ,'end_time', 'sampling_rate', 'delta', 'npts' ,'calib' ,'format','fileInfo' ,'trace' ]

class StationInfoPSerializer(serializers.ModelSerializer):

    class Meta:
        model = StationInfo
        fields = "__all__"

    