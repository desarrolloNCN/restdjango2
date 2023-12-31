

from .models import SeismicData, UploadFile, PlotData, TraceData

from django.contrib.auth.models import Group, User
from django.http import JsonResponse
from django.shortcuts import render

from rest_framework import permissions, viewsets, status
from rest_framework.views import APIView
from rest_framework.response import Response

from restapi.serializers import GroupSerializer, UserSerializer, SeismicDataSerializer, FileUploadSerializer, PlotDataSerializer, TraceDataSerializer

import obspy
import os
import uuid

from datetime import datetime
from scipy import integrate
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

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
        file = request.FILES.get('file')
        data_str = request.data.get('data')

        if not file and not data_str:
            return Response({'message': 'No se proporcionó datos para Lectura'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if data_str:
                sts = obspy.read(data_str)
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        tr_info = []

        for i, tr in enumerate(sts):
            tr_info.append({
                'network': tr.stats.network,
                'station': tr.stats.station,
                'location': tr.stats.location,
                'channel': tr.stats.channel,
                'starttime': str(tr.stats.starttime),
                'endtime': str(tr.stats.endtime),
                'sampling_rate': tr.stats.sampling_rate,
                'delta': tr.stats.delta,
                'npts': tr.stats.npts,
                'calib': tr.stats.calib,
                'format': tr.stats._format,
            })

        seismic_record_instance = SeismicData.objects.create(
            data=tr_info,
        )

        serializer = self.get_serializer(seismic_record_instance)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

class FileUploadView(viewsets.ModelViewSet):
    queryset = UploadFile.objects.all()
    serializer_class = FileUploadSerializer

    def post(self, request, *args, **kwargs):
        data_type = request.data.get('data_type')

        if data_type == 'file':
            file_serializer = FileUploadSerializer(data=request.data)

            if file_serializer.is_valid():
                ext = file_serializer.validated_data['file'].name.split('.')[-1]
                unique_filename = f"{uuid.uuid4().hex}.{ext}"

                file_serializer.validated_data['file'].name = os.path.join('uploads/', unique_filename)

                file_serializer.save()

                return Response({
                    'id': file_serializer.data['id'],
                    'file_name': file_serializer.data['file'].name
                }, status=status.HTTP_201_CREATED)
            
            else:
                return Response(file_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        elif data_type == 'string':
            string_data = request.data.get('string_data')

            if string_data:
                # Guardar la cadena en tu modelo directamente
                UploadFile.objects.create(string_data=string_data)

                return Response({'success': 'Cadena guardada correctamente.'}, status=status.HTTP_201_CREATED)
            else:
                return Response({'error': 'El campo "string_data" es necesario para el tipo de datos "string".'}, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({'error': 'Tipo de datos no admitido.'}, status=status.HTTP_400_BAD_REQUEST)

class PlotFileView(viewsets.ModelViewSet):
    queryset = PlotData.objects.all()
    serializer_class = PlotDataSerializer

    def create(self, request, *args, **kwargs):
        data_str = request.data.get('data')
        station_data = request.data.get('station_selected')
        channel_data = request.data.get('channel_selected')
        if not data_str and not station_data and not channel_data:
            return Response({'message': 'No se proporcionaron datos suficientes para la lectura'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if data_str:
                sts = obspy.read(data_str)
                sts.detrend(type='linear')
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        saved_instances = []

        for station in sts:
            if station.stats.station == station_data and station.stats.channel == channel_data:
                data_sts = station.data
                sampling = station.stats.sampling_rate
                tiempo = np.arange(len(data_sts)) / sampling

                acceleration = np.gradient(np.gradient(data_sts, 1/sampling), 1/sampling)

                plt.figure(figsize=(10, 4))
                plt.plot(tiempo, acceleration, label='Aceleración', color='b', linewidth=0.5)
                plt.title(station)
                plt.xlabel('Tiempo (s)')
                plt.ylabel('Magnitud')
                plt.legend()
                plt.grid(True)

                current_datetime = datetime.now().strftime('%Y%m%d_%H%M%S')

                image_filename = f'{station.stats.station}_{station.stats.channel}_{current_datetime}.png'
                image_path = os.path.join('media/seismic_plots/', image_filename)

                plt.savefig(image_path)
                plt.close()

                media_image_path = os.path.join('/seismic_plots/', image_filename)

                seismic_record_instance = PlotData.objects.create(image_path=media_image_path)
                saved_instances.append(seismic_record_instance)

        serializer = self.get_serializer(saved_instances, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
class TracesDataView(viewsets.ModelViewSet):
    queryset = TraceData.objects.all()
    serializer_class = TraceDataSerializer

    def create(self, request, *args, **kwargs):
        data_str = request.data.get('data')
        station_data = request.data.get('station_selected')
        channel_data = request.data.get('channel_selected')

        if not data_str:
            return Response({'message': 'No se proporcionaron datos suficientes para la lectura'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if data_str:
                sts = obspy.read(data_str)
                sts.detrend(type='linear')
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        saved_instances = []

        for station in sts:
            if station.stats.station == station_data and station.stats.channel == channel_data:
                data_sts = station.data
                sampling = station.stats.sampling_rate
                tiempo = np.arange(len(data_sts)) / sampling

                data_vel = np.cumsum(data_sts) * tiempo
                data_dsp = np.cumsum(data_vel) * tiempo

                seismic_record_instance = TraceData(traces_a=data_sts.tolist(), traces_v=data_vel.tolist(), traces_d = data_dsp.tolist() , tiempo_a=tiempo.tolist())
                saved_instances.append(seismic_record_instance)

        serializer = self.get_serializer(saved_instances, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)