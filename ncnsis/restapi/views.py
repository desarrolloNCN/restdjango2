from django.http import JsonResponse
from django.shortcuts import render
from django.contrib.auth.models import Group, User
from rest_framework import permissions, viewsets
from rest_framework.response import Response

from restapi.serializers import GroupSerializer, UserSerializer, SeismicDataSerializer

from .models import SeismicData

import obspy


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]

class SeismicDataViewSet(viewsets.ModelViewSet):
    queryset = SeismicData.objects.all()
    serializer_class = SeismicDataSerializer
    def create(self, request, *args, **kwargs):
        if 'file' in request.FILES:    
            file = request.FILES['file']
            try:
                sts = obspy.read(file)
            except Exception as e:    
                return Response({'error': f'Error => {str(e)}'})
            tr_info = []

            for i, tr in enumerate(sts):
                tr_info.append({
                    'nombre' : f'Canal {i + 1}',
                    'network' : tr.stats.network,
                    'estacion' : tr.stats.station,
                    'sampling' : tr.stats.sampling_rate
                })
            seismic_record_instance = SeismicData.objects.create(
                data=tr_info,
                file_name=file.name
            )
            serializer = self.get_serializer(seismic_record_instance)
            return Response(serializer.data)
        return Response({'error': 'No hay archivo'})
