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


# ------------------------------------------------------------

class CalibTracesSerializer(serializers.ModelSerializer):
    class Meta:
        model = CalibTraces
        fields = "__all__"

class FileUploadUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadFileUser
        fields = "__all__"

# ------------------------------------------------------------

class ProyectoFilesSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProyectoFiles
        fields = "__all__"

class ProyectoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proyecto
        fields = "__all__"


# ------------------------------------------------------------


class FileInfoSerializer(serializers.ModelSerializer):
    files = ProyectoFilesSerializer()  

    class Meta:
        model = FileInfo
        fields = "__all__"

class TracesSerializer(serializers.ModelSerializer):
    class Meta:
        model = Traces
        fields = "__all__"

class StationInfoSerializer(serializers.ModelSerializer):
    fileInfo = FileInfoSerializer()
    trace = TracesSerializer()

    class Meta:
        model = StationInfo
        fields = "__all__"
