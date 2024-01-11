from django.contrib.auth.models import Group, User
from rest_framework import serializers

from .models import SeismicData, UploadFile, PlotData, TraceData, TraceDataBaseline, TraceFilterline


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