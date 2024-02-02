

from .models import *
from restapi.serializers import *

from django.contrib.auth.models import Group, User
from django.contrib.auth import logout

from rest_framework import permissions, viewsets, authentication, status
from rest_framework.views import APIView
from rest_framework.response import Response

from rest_framework.exceptions import APIException

import obspy
import os
import uuid

from obspy import read_inventory

from datetime import datetime

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
    permission_classes = [permissions.IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        data_str = request.data.get('data')

        if not data_str:
            raise APIException('No se proporcionó datos para Lectura')

        try:
            sts = obspy.read(data_str)
            tr_info = self.extract_tr_info(sts)
            inventory = self.read_inventory_safe(data_str)
            combined_info = self.combine_tr_and_inv_info(tr_info, inventory)

            seismic_record_instance = SeismicData(data=combined_info)
            serializer = self.get_serializer(seismic_record_instance)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

    def extract_tr_info(self, sts):
        tr_info = []
        for tr in sts:
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
        return tr_info

    def read_inventory_safe(self, data_str):
        try:
            return read_inventory(data_str)
        except Exception:
            return None

    def combine_tr_and_inv_info(self, tr_info, inventory):
        combined_info = tr_info
        if inventory:
            inv_info = []
            for network in inventory:
                for station in network:
                    for channel in station:
                        inv_info.append({
                            'network': network.code,
                            'station': station.code,
                            'location': channel.location_code,
                            'f_calib': channel.response.instrument_sensitivity.value,
                            'und_calib': channel.response.instrument_sensitivity.input_units
                        })
            combined_info = []
            for tr_item in tr_info:
                for inv_item in inv_info:
                    if (tr_item['network'] == inv_item['network'] and
                        tr_item['station'] == inv_item['station'] and
                        tr_item['location'] == inv_item['location']):
                        combined_info.append({**tr_item, **inv_item})
                        break
        return combined_info
    
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
                #sts.detrend(type='linear')
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
    serializer_class = TraceDataBaselineSerializer

    def create(self, request, *args, **kwargs):
        data_str = request.data.get('data')
        station_data = request.data.get('station_selected')
        channel_data = request.data.get('channel_selected')

        if not data_str:
            return Response({'message': 'No se proporcionaron datos suficientes para la lectura'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if data_str:
                sts = obspy.read(data_str)
                inventory = self.read_inventory_safe(data_str)
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        saved_instances = []

        f_calib = None
        if inventory:
            for network in inventory:
                for station_inv in network:
                    for channel_inv in station_inv:
                        if (station_inv.code == station_data and 
                            channel_inv.code == channel_data):
                            f_calib = channel_inv.response.instrument_sensitivity.value
                            break
                    if f_calib:
                        break
                if f_calib:
                    break

        for station in sts:
            if (station.stats.station == station_data and station.stats.channel == channel_data):

                if f_calib:
                    data_sts = np.round(station.data, 3) * station.stats.calib * 1/f_calib
                else:
                    data_sts = np.round(station.data, 3) * station.stats.calib

                sampling = station.stats.sampling_rate

                tiempo = np.round(np.arange(0, station.stats.npts / sampling, station.stats.delta), 2)

                int_sts = station.integrate(method='cumtrapz')

                data_vel = np.round(int_sts.data * station.stats.calib * 1 / f_calib, 3) if f_calib else np.round(int_sts.data * station.stats.calib, 3)
                data_dsp = np.round(int_sts.integrate(method='cumtrapz').data * station.stats.calib * 1 / f_calib, 3) if f_calib else np.round(int_sts.integrate(method='cumtrapz').data * station.stats.calib, 3)

                seismic_record_instance = TraceData(
                    traces_a=data_sts.tolist(),
                    traces_v=data_vel.tolist(),
                    traces_d=data_dsp.tolist(),
                    tiempo_a=tiempo.tolist()
                )
                saved_instances.append(seismic_record_instance)

        serializer = self.get_serializer(saved_instances, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def read_inventory_safe(self, data_str):
        try:
            return read_inventory(data_str)
        except Exception:
            return None
        


class TracesDataBaseLineView(viewsets.ModelViewSet):
    queryset = TraceDataBaseline.objects.all()
    serializer_class = TraceDataSerializer

    def create(self, request, *args, **kwargs):
        data_str = request.data.get('data')
        station_data = request.data.get('station_selected')
        channel_data = request.data.get('channel_selected')
        baseline_type = request.data.get('base_line' , '')
        filter_type = request.data.get('filter_type', '')
        freq_min = request.data.get('freq_min', '')
        freq_max = request.data.get('freq_max', '')
        corner = request.data.get('corner', '')
        t_min = request.data.get('t_min')
        t_max = request.data.get('t_max')
        
        if not data_str:
            return Response({'message': 'No se proporcionaron datos suficientes para la lectura'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if data_str:
                sts = obspy.read(data_str)
                inventory = self.read_inventory_safe(data_str)

                if filter_type and freq_min and freq_max and corner:
                    sts.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=True )
                elif t_min and t_max:
                    min = obspy.UTCDateTime(t_min)
                    max = obspy.UTCDateTime(t_max)
                    sts.trim(min,max)
                sts.detrend(type=baseline_type)
                
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        saved_instances = []

        f_calib = None

        if inventory:
            for network in inventory:
                for station_inv in network:
                    for channel_inv in station_inv:
                        if (station_inv.code == station_data and 
                            channel_inv.code == channel_data):
                            f_calib = channel_inv.response.instrument_sensitivity.value
                            break
                    if f_calib:
                        break
                if f_calib:
                    break

        for station in sts:
            if (station.stats.station == station_data and station.stats.channel == channel_data):

                if f_calib:
                    data_sts = np.round(station.data, 3) * station.stats.calib * 1/f_calib
                else:
                    data_sts = np.round(station.data, 3) * station.stats.calib

                sampling = station.stats.sampling_rate

                tiempo = np.round(np.arange(0, station.stats.npts / sampling, station.stats.delta), 2)

                int_sts = station.integrate(method='cumtrapz')

                data_vel = np.round(int_sts.data * station.stats.calib * 1 / f_calib, 3) if f_calib else np.round(int_sts.data * station.stats.calib, 3)
                data_dsp = np.round(int_sts.integrate(method='cumtrapz').data * station.stats.calib * 1 / f_calib, 3) if f_calib else np.round(int_sts.integrate(method='cumtrapz').data * station.stats.calib, 3)

                seismic_record_instance = TraceData(
                    traces_a=data_sts.tolist(),
                    traces_v=data_vel.tolist(),
                    traces_d=data_dsp.tolist(),
                    tiempo_a=tiempo.tolist()
                )
                saved_instances.append(seismic_record_instance)

        serializer = self.get_serializer(saved_instances, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def read_inventory_safe(self, data_str):
        try:
            return read_inventory(data_str)
        except Exception:
            return None


    
class TracesDataFilterView(viewsets.ModelViewSet):
    queryset = TraceFilterline.objects.all()
    serializer_class = TraceFilterSerializer

    def create(self, request, *args, **kwargs):
        data_str = request.data.get('data')
        station_data = request.data.get('station_selected')
        channel_data = request.data.get('channel_selected')
        baseline_type = request.data.get('base_line' , '')
        filter_type = request.data.get('filter_type', '')
        freq_min = request.data.get('freq_min', '')
        freq_max = request.data.get('freq_max', '')
        corner = request.data.get('corner', '')
        t_min = request.data.get('t_min')
        t_max = request.data.get('t_max')
        
        if not data_str:
            return Response({'message': 'No se proporcionaron datos suficientes para la lectura'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if data_str:
                sts = obspy.read(data_str)
                inventory = self.read_inventory_safe(data_str)
                if baseline_type:
                    sts.detrend(type=baseline_type)
                elif t_min and t_max:
                    min = obspy.UTCDateTime(t_min)
                    max = obspy.UTCDateTime(t_max)
                    sts.trim(min,max)
                sts.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner))
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        saved_instances = []

        f_calib = None

        if inventory:
            for network in inventory:
                for station_inv in network:
                    for channel_inv in station_inv:
                        if (station_inv.code == station_data and 
                            channel_inv.code == channel_data):
                            f_calib = channel_inv.response.instrument_sensitivity.value
                            break
                    if f_calib:
                        break
                if f_calib:
                    break

        for station in sts:
            if (station.stats.station == station_data and station.stats.channel == channel_data):

                if f_calib:
                    data_sts = np.round(station.data, 3) * station.stats.calib * 1/f_calib
                else:
                    data_sts = np.round(station.data, 3) * station.stats.calib

                sampling = station.stats.sampling_rate

                tiempo = np.round(np.arange(0, station.stats.npts / sampling, station.stats.delta), 2)

                int_sts = station.integrate(method='cumtrapz')

                data_vel = np.round(int_sts.data * station.stats.calib * 1 / f_calib, 3) if f_calib else np.round(int_sts.data * station.stats.calib, 3)
                data_dsp = np.round(int_sts.integrate(method='cumtrapz').data * station.stats.calib * 1 / f_calib, 3) if f_calib else np.round(int_sts.integrate(method='cumtrapz').data * station.stats.calib, 3)

                seismic_record_instance = TraceData(
                    traces_a=data_sts.tolist(),
                    traces_v=data_vel.tolist(),
                    traces_d=data_dsp.tolist(),
                    tiempo_a=tiempo.tolist()
                )
                saved_instances.append(seismic_record_instance)

        serializer = self.get_serializer(saved_instances, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def read_inventory_safe(self, data_str):
        try:
            return read_inventory(data_str)
        except Exception:
            return None


    
class TracesTrimView(viewsets.ModelViewSet):
    queryset = TraceTrimline.objects.all()
    serializer_class = TraceTrimSerializer

    def create(self, request, *args, **kwargs):
        data_str = request.data.get('data')
        station_data = request.data.get('station_selected')
        channel_data = request.data.get('channel_selected')
        baseline_type = request.data.get('base_line' , '')
        filter_type = request.data.get('filter_type', '')
        freq_min = request.data.get('freq_min', '')
        freq_max = request.data.get('freq_max', '')
        corner = request.data.get('corner', '')
        t_min = request.data.get('t_min')
        t_max = request.data.get('t_max')
        
        if not data_str:
            return Response({'message': 'No se proporcionaron datos suficientes para la lectura'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if data_str:
                sts  = obspy.read(data_str)
                inventory = self.read_inventory_safe(data_str)
                if baseline_type:
                    sts.detrend(type=baseline_type)
                elif filter_type and freq_min and freq_max and corner:
                    sts.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=True )
                elif t_min and t_max:
                    min = obspy.UTCDateTime(t_min)
                    max = obspy.UTCDateTime(t_max)
                    sts.trim(min,max)
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        saved_instances = []

        f_calib = None

        if inventory:
            for network in inventory:
                for station_inv in network:
                    for channel_inv in station_inv:
                        if (station_inv.code == station_data and 
                            channel_inv.code == channel_data):
                            f_calib = channel_inv.response.instrument_sensitivity.value
                            break
                    if f_calib:
                        break
                if f_calib:
                    break

        for station in sts:
            if (station.stats.station == station_data and station.stats.channel == channel_data):

                if f_calib:
                    data_sts = np.round(station.data, 3) * station.stats.calib * 1/f_calib
                else:
                    data_sts = np.round(station.data, 3) * station.stats.calib

                sampling = station.stats.sampling_rate

                tiempo = np.round(np.arange(0, station.stats.npts / sampling, station.stats.delta), 2)

                int_sts = station.integrate(method='cumtrapz')

                data_vel = np.round(int_sts.data * station.stats.calib * 1 / f_calib, 3) if f_calib else np.round(int_sts.data * station.stats.calib, 3)
                data_dsp = np.round(int_sts.integrate(method='cumtrapz').data * station.stats.calib * 1 / f_calib, 3) if f_calib else np.round(int_sts.integrate(method='cumtrapz').data * station.stats.calib, 3)

                seismic_record_instance = TraceData(
                    traces_a=data_sts.tolist(),
                    traces_v=data_vel.tolist(),
                    traces_d=data_dsp.tolist(),
                    tiempo_a=tiempo.tolist()
                )
                saved_instances.append(seismic_record_instance)

        serializer = self.get_serializer(saved_instances, many=True)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def read_inventory_safe(self, data_str):
        try:
            return read_inventory(data_str)
        except Exception:
            return None