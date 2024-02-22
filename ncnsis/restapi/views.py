

from posixpath import splitext
import subprocess
import tempfile
from django.conf import settings
from .models import *
from restapi.serializers import *

from django.contrib.auth.models import Group, User
from django.contrib.auth import logout
from django.http import HttpResponse

from rest_framework import permissions, viewsets, authentication, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound
from rest_framework.decorators import action
from rest_framework.exceptions import APIException
from rest_framework.decorators import api_view


import obspy
import os
import uuid
import pyrotd


from obspy import Stream, Trace, UTCDateTime, read_inventory
from astropy.convolution import convolve, Gaussian1DKernel, Box1DKernel

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
    
    def create(self, request, *args, **kwargs):
        data_str = request.data.get('data')

        if not data_str:
            raise APIException('No se proporcionó datos para Lectura')

        try:
            sts = obspy.read(data_str)
            sts.merge(method=1, fill_value= 'latest')
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
    serializer_class = TraceDataSerializer

    def create(self, request, *args, **kwargs):
        data_str = request.data.get('data')
        station_data = request.data.get('station_selected')
        channel_data = request.data.get('channel_selected')
        unit = request.data.get('unit', '')

        if not data_str:
            return Response({'message': 'No se proporcionaron datos suficientes para la lectura'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if data_str:
                sts = obspy.read(data_str)

                sts.merge(method=1, fill_value= 'latest')

                inventory = self.read_inventory_safe(data_str)
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        saved_instances = []
        unit_found = ''

        if inventory:
            for net in inventory:
                for sta in net:
                    if(sta.code == station_data):
                        for cha in sta:
                            unit_found = cha.response.instrument_sensitivity.input_units

            sts.attach_response(inventory)            
            sts.remove_sensitivity()
            
            
        for station in sts:
            if (station.stats.station == station_data and station.stats.channel == channel_data):
                
                indice_traza = 0
                format_file = station.stats._format

                for i, traza in enumerate(sts):
                    if traza.stats.channel == station.stats.channel:
                        indice_traza = i
                        break

                sampling = station.stats.sampling_rate
                tiempo = np.round(np.arange(0, station.stats.npts / sampling, station.stats.delta), 4)

                st1 = station.copy()

                st2 = st1.copy()
                st3 = st2.integrate(method='cumtrapz')

                st4 = st3.copy()
                st5 = st4.integrate(method='cumtrapz')
        

                filename = data_str.split('/')[-1]
                extension = splitext(filename)[1]

                if unit == 'g':
                    st1_data = st1.data * station.stats.calib 
                    st3_data = st3.data * station.stats.calib 
                    st5_data = st5.data * station.stats.calib 
                    unit_a, unit_v, unit_d = 'G', 'cm/s', 'cm'
                else:
                    st1_data = st1.data * station.stats.calib 
                    st3_data = st3.data * station.stats.calib 
                    st5_data = st5.data * station.stats.calib                    
                    if unit == 'm' or unit_found == 'M/S**2':
                         unit_a, unit_v, unit_d = 'm/s2', 'm/s', 'm'
                    elif unit == 'gal' or unit_found == 'CM/S**2':
                         unit_a, unit_v, unit_d= 'cm/s2', 'cm/s', 'cm'
                    else:
                         unit_a, unit_v, unit_d = 'unk', 'unk', 'unk'

                if extension == 'evt':
                    st1_data *= 100 
                    st3_data *= 100
                    st5_data *= 100
                
                try:
                    if station.stats.reftek130:
                        tbw = float(station.stats.reftek130.channel_true_bit_weights[indice_traza].split()[0])
                        ch_gain = float(station.stats.reftek130.channel_gain_code[indice_traza])
                        vpu = station.stats.reftek130.channel_sensor_vpu[indice_traza]
                        factor_conver_psc = 1/ (ch_gain*vpu*1000000/(tbw*9.81))
                        st1_data *= factor_conver_psc * 100
                        st3_data *= factor_conver_psc * 100
                        st5_data *= factor_conver_psc * 100
                except AttributeError:
                    print("")


                max_abs_a_value = max(np.max(st1_data), np.min(st1_data), key=abs)
                pga_a_value = max_abs_a_value

                max_abs_v_value = max(np.max(st3_data), np.min(st3_data), key=abs)
                pga_v_value = max_abs_v_value

                max_abs_d_value = max(np.max(st5_data), np.min(st5_data), key=abs)
                pga_d_value = max_abs_d_value

                # if unit == 'gal':
                #     unit_a = "cm/s2"
                #     unit_v = "cm/s"
                #     unit_d = "cm"
                # if unit == 'm':
                #     unit_a = "m/s2"
                #     unit_v = "m/s"
                #     unit_d = "m"
                # if unit == 'g':
                #     unit_a = "G"
                #     unit_v = "cm/s"
                #     unit_d = "cm"
                # if unit == '':
                #     unit_a = "unk"
                #     unit_v = "unk"
                #     unit_d = "unk"   

                # data_vel = np.round(st3.data * station.stats.calib * (1 / f_calib), 4) if f_calib else np.round(st3.data * station.stats.calib, 4)
                # data_dsp = np.round(st5.data * station.stats.calib * (1 / f_calib), 4) if f_calib else np.round(st5.data * station.stats.calib, 4)

                seismic_record_instance = TraceData(
                    formato = format_file,

                    trace_a_unit  =  unit_a,
                    traces_a = st1_data.tolist(),
                    peak_a   = pga_a_value,

                    trace_v_unit = unit_v,
                    traces_v = st3_data.tolist(),
                    peak_v   = pga_v_value,

                    trace_d_unit = unit_d,
                    traces_d = st5_data.tolist(),
                    peak_d   = pga_d_value,

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
    queryset = TraceData.objects.all()
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
        zero_ph = request.data.get('zero', False)
        t_min = request.data.get('t_min')
        t_max = request.data.get('t_max')
        convert_from_unit = request.data.get('unit_from', '')
        convert_to_unit = request.data.get('unit_to', '')
        if not data_str:
            return Response({'message': 'No se proporcionaron datos suficientes para la lectura'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if data_str:
                sts = obspy.read(data_str)
                sts.merge(method=1, fill_value= 'latest')
                inventory = self.read_inventory_safe(data_str)
                
                if t_min and t_max:
                    min_time = obspy.UTCDateTime(t_min)
                    max_time = obspy.UTCDateTime(t_max)
                    sts.trim(min_time,max_time)

                sts.detrend(type=baseline_type)

        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        saved_instances = []

        f_calib = None

        if inventory:
            sts.attach_response(inventory)
            sts.remove_sensitivity()

        for station in sts:
            if (station.stats.station == station_data and station.stats.channel == channel_data):
                
                indice_traza = 0

                for i, traza in enumerate(sts):
                    if traza.stats.channel == station.stats.channel:
                        indice_traza = i
                        break

                sampling = station.stats.sampling_rate
                tiempo = np.round(np.arange(0, station.stats.npts / sampling, station.stats.delta), 4)

                st1 = station.copy()
                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st1.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)

                st2 = st1.copy()
                st3 = st2.integrate(method='cumtrapz')

                if baseline_type:
                   st3.detrend(type=baseline_type)
                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st3.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)
                

                # if filter_type == 'bandpass' or filter_type == 'bandstop' :
                #     st3.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner))

                st4 = st3.copy()
                st5 = st4.integrate(method='cumtrapz')
                if baseline_type:
                   st5.detrend(type=baseline_type)
                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st5.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)


                filename = data_str.split('/')[-1]
                extension = splitext(filename)[1]
                
                if convert_from_unit:
                    if convert_from_unit == 'gal':
                        if convert_to_unit == 'm':
                            st1_data = st1.data * station.stats.calib * 0.01
                            st3_data = st3.data * station.stats.calib * 0.01
                            st5_data = st5.data * station.stats.calib * 0.01
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'gal' or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'g':
                            st1_data = st1.data * station.stats.calib * 0.001019
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                        
                    if convert_from_unit == 'm':
                        if convert_to_unit == 'gal':
                            st1_data = st1.data * station.stats.calib * 100
                            st3_data = st3.data * station.stats.calib * 100
                            st5_data = st5.data * station.stats.calib * 100
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'm'  or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'g':
                            st1_data = st1.data * station.stats.calib * 0.101972
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                    if convert_from_unit == 'g':
                        if convert_to_unit == 'gal':
                            st1_data = st1.data * station.stats.calib * 980.66
                            st3_data = st3.data * station.stats.calib * 100
                            st5_data = st5.data * station.stats.calib * 100
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                        if convert_to_unit == 'm':
                            st1_data = st1.data * station.stats.calib * 9.8066
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                        if convert_to_unit == 'g' or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'unk', 'unk'
                    if convert_from_unit == '' or convert_from_unit == 'null':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'unk', 'unk', 'unk'
                else:
                    st1_data = st1.data * station.stats.calib * 1
                    st3_data = st3.data * station.stats.calib * 1
                    st5_data = st5.data * station.stats.calib * 1
                    cuv1, cuv2, cuv3 = '-unk', '-unk', '-unk'

                if extension == '.evt':
                    st1_data *= 100 
                    st3_data *= 100
                    st5_data *= 100
                
                try:
                    if station.stats.reftek130:
                        tbw = float(station.stats.reftek130.channel_true_bit_weights[indice_traza].split()[0])
                        ch_gain = float(station.stats.reftek130.channel_gain_code[indice_traza])
                        vpu = station.stats.reftek130.channel_sensor_vpu[indice_traza]
                        factor_conver_psc = 1/ (ch_gain*vpu*1000000/(tbw*9.81))
                        st1_data *= factor_conver_psc * 100
                        st3_data *= factor_conver_psc * 100
                        st5_data *= factor_conver_psc * 100
                except AttributeError:
                    print("")

                max_abs_a_value = max(np.max(st1_data), np.min(st1_data), key=abs)
                pga_a_value = max_abs_a_value

                max_abs_v_value = max(np.max(st3_data), np.min(st3_data), key=abs)
                pga_v_value = max_abs_v_value

                max_abs_d_value = max(np.max(st5_data), np.min(st5_data), key=abs)
                pga_d_value = max_abs_d_value

                seismic_record_instance = TraceData(
                    trace_a_unit=cuv1,
                    traces_a=st1_data.tolist(),
                    peak_a=pga_a_value,
                    trace_v_unit=cuv2,
                    traces_v=st3_data.tolist(),
                    peak_v=pga_v_value,
                    trace_d_unit=cuv3,
                    traces_d=st5_data.tolist(),
                    peak_d=pga_d_value,
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
    queryset = TraceData.objects.all()
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
        zero_ph = request.data.get('zero', False)
        t_min = request.data.get('t_min')
        t_max = request.data.get('t_max')
        convert_from_unit = request.data.get('unit_from', '')
        convert_to_unit = request.data.get('unit_to', '')
        if not data_str:
            return Response({'message': 'No se proporcionaron datos suficientes para la lectura'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if data_str:
                sts = obspy.read(data_str)
                sts.merge(method=1, fill_value= 'latest')
                inventory = self.read_inventory_safe(data_str)

                if baseline_type:
                    sts.detrend(type=baseline_type)

                if t_min and t_max:
                    min_time = obspy.UTCDateTime(t_min)
                    max_time = obspy.UTCDateTime(t_max)
                    sts.trim(min_time,max_time)
                
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        saved_instances = []

        f_calib = None

        if inventory:
            sts.attach_response(inventory)
            sts.remove_sensitivity()

        for station in sts:
            if (station.stats.station == station_data and station.stats.channel == channel_data):

                indice_traza = 0
                formato_file = station.stats._format

                for i, traza in enumerate(sts):
                    if traza.stats.channel == station.stats.channel:
                        indice_traza = i
                        break

                sampling = station.stats.sampling_rate
                tiempo = np.round(np.arange(0, station.stats.npts / sampling, station.stats.delta), 4)

                st1 = station.copy()
                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st1.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)

                st2 = st1.copy()
                st3 = st2.integrate(method='cumtrapz')
                # if filter_type == 'bandpass' or filter_type == 'bandstop' :
                #     st3.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zero_ph)
                if baseline_type:
                   st3.detrend(type=baseline_type)

                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st3.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)
                

                st4 = st3.copy()
                st5 = st4.integrate(method='cumtrapz')
                if baseline_type:
                   st5.detrend(type=baseline_type)
                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st5.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)
                
                # if filter_type == 'bandpass' or filter_type == 'bandstop' :
                #     st5.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zero_ph)
                
                filename = data_str.split('/')[-1]
                extension = splitext(filename)[1]

                if convert_from_unit:
                    if convert_from_unit == 'gal':
                        if convert_to_unit == 'm':
                            st1_data = st1.data * station.stats.calib * 0.01
                            st3_data = st3.data * station.stats.calib * 0.01
                            st5_data = st5.data * station.stats.calib * 0.01
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'gal' or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'g':
                            st1_data = st1.data * station.stats.calib * 0.001019
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                    if convert_from_unit == 'm':
                        if convert_to_unit == 'gal':
                            st1_data = st1.data * station.stats.calib * 100
                            st3_data = st3.data * station.stats.calib * 100
                            st5_data = st5.data * station.stats.calib * 100
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'm'  or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'g':
                            st1_data = st1.data * station.stats.calib * 0.101972
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                    if convert_from_unit == 'g':
                        if convert_to_unit == 'gal':
                            st1_data = st1.data * station.stats.calib * 980.66
                            st3_data = st3.data * station.stats.calib * 100
                            st5_data = st5.data * station.stats.calib * 100
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                        if convert_to_unit == 'm':
                            st1_data = st1.data * station.stats.calib * 9.8066
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                        if convert_to_unit == 'g' or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'unk', 'unk'
                    if convert_from_unit == '' or convert_from_unit == 'null':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'unk', 'unk', 'unk'
                else:
                    st1_data = st1.data * station.stats.calib * 1
                    st3_data = st3.data * station.stats.calib * 1
                    st5_data = st5.data * station.stats.calib * 1
                    cuv1, cuv2, cuv3 = '-unk', '-unk', '-unk'
                
                if extension == '.evt':
                    st1_data *= 100 
                    st3_data *= 100
                    st5_data *= 100
                    cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                
                try:
                    if station.stats.reftek130:
                        tbw = float(station.stats.reftek130.channel_true_bit_weights[indice_traza].split()[0])
                        ch_gain = float(station.stats.reftek130.channel_gain_code[indice_traza])
                        vpu = station.stats.reftek130.channel_sensor_vpu[indice_traza]
                        factor_conver_psc = 1/ (ch_gain*vpu*1000000/(tbw*9.81))
                        st1_data *= factor_conver_psc * 100
                        st3_data *= factor_conver_psc * 100
                        st5_data *= factor_conver_psc * 100
                except AttributeError:
                    print("")
            
                max_abs_a_value = max(np.max(st1_data), np.min(st1_data), key=abs)
                pga_a_value = max_abs_a_value

                max_abs_v_value = max(np.max(st3_data), np.min(st3_data), key=abs)
                pga_v_value = max_abs_v_value

                max_abs_d_value = max(np.max(st5_data), np.min(st5_data), key=abs)
                pga_d_value = max_abs_d_value

                # data_vel = np.round(st3.data * station.stats.calib * (1 / f_calib), 4) if f_calib else np.round(st3.data * station.stats.calib, 4)
                # data_dsp = np.round(st5.data * station.stats.calib * (1 / f_calib), 4) if f_calib else np.round(st5.data * station.stats.calib, 4)

                seismic_record_instance = TraceData(
                    formato = formato_file,
                    trace_a_unit=cuv1,
                    traces_a=st1_data.tolist(),
                    peak_a=pga_a_value,
                    trace_v_unit=cuv2,
                    traces_v=st3_data.tolist(),
                    peak_v=pga_v_value,
                    trace_d_unit=cuv3,
                    traces_d=st5_data.tolist(),
                    peak_d=pga_d_value,
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
    queryset = TraceData.objects.all()
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
        zero_ph = request.data.get('zero', False)
        t_min = request.data.get('t_min')
        t_max = request.data.get('t_max')
        convert_unit = request.data.get('unit', '')
        convert_from_unit = request.data.get('unit_from', '')
        convert_to_unit = request.data.get('unit_to', '')
        if not data_str:
            return Response({'message': 'No se proporcionaron datos suficientes para la lectura'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if data_str:
                sts  = obspy.read(data_str)
                sts.merge(method=1, fill_value= 'latest')
                inventory = self.read_inventory_safe(data_str)

                if baseline_type:
                    sts.detrend(type=baseline_type)
                if t_min and t_max:
                    min_time = obspy.UTCDateTime(t_min)
                    max_time = obspy.UTCDateTime(t_max)
                    sts.trim(min_time,max_time)
                    
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        saved_instances = []

        f_calib = None
        if inventory:
            sts.attach_response(inventory)
            sts.remove_sensitivity()

        for station in sts:
            if (station.stats.station == station_data and station.stats.channel == channel_data):
                
                indice_traza = 0

                for i, traza in enumerate(sts):
                    if traza.stats.channel == station.stats.channel:
                        indice_traza = i
                        break

                sampling = station.stats.sampling_rate
                tiempo = np.round(np.arange(0, station.stats.npts / sampling, station.stats.delta), 4)

                st1 = station.copy()

                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st1.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)

                st2 = st1.copy()
                st3 = st2.integrate(method='cumtrapz')

                if baseline_type:
                   st3.detrend(type=baseline_type)

                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st3.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)
                
                # if filter_type == 'bandpass' or filter_type == 'bandstop' :
                #     st3.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=True)

                st4 = st3.copy()
                st5 = st4.integrate(method='cumtrapz')
                if baseline_type:
                   st5.detrend(type=baseline_type)

                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st5.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)
                # if filter_type == 'bandpass' or filter_type == 'bandstop' :
                #     st5.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=True)
                filename = data_str.split('/')[-1]
                extension = splitext(filename)[1]

                if convert_from_unit:
                    if convert_from_unit == 'gal':
                        if convert_to_unit == 'm':
                            st1_data = st1.data * station.stats.calib * 0.01
                            st3_data = st3.data * station.stats.calib * 0.01
                            st5_data = st5.data * station.stats.calib * 0.01
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'gal' or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'g':
                            st1_data = st1.data * station.stats.calib * 0.001019
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                    if convert_from_unit == 'm':
                        if convert_to_unit == 'gal':
                            st1_data = st1.data * station.stats.calib * 100
                            st3_data = st3.data * station.stats.calib * 100
                            st5_data = st5.data * station.stats.calib * 100
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'm'  or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'g':
                            st1_data = st1.data * station.stats.calib * 0.101972
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                    if convert_from_unit == 'g':
                        if convert_to_unit == 'gal':
                            st1_data = st1.data * station.stats.calib * 980.66
                            st3_data = st3.data * station.stats.calib * 100
                            st5_data = st5.data * station.stats.calib * 100
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                        if convert_to_unit == 'm':
                            st1_data = st1.data * station.stats.calib * 9.8066
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                        if convert_to_unit == 'g' or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'unk', 'unk'
                    if convert_from_unit == '' or convert_from_unit == 'null':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'unk', 'unk', 'unk'
                else:
                    st1_data = st1.data * station.stats.calib * 1
                    st3_data = st3.data * station.stats.calib * 1
                    st5_data = st5.data * station.stats.calib * 1
                    cuv1, cuv2, cuv3 = '-unk', '-unk', '-unk'
                
                if extension == '.evt':
                    st1_data *= 100 
                    st3_data *= 100
                    st5_data *= 100
                
                try:
                    if station.stats.reftek130:
                        tbw = float(station.stats.reftek130.channel_true_bit_weights[indice_traza].split()[0])
                        ch_gain = float(station.stats.reftek130.channel_gain_code[indice_traza])
                        vpu = station.stats.reftek130.channel_sensor_vpu[indice_traza]
                        factor_conver_psc = 1/ (ch_gain*vpu*1000000/(tbw*9.81))
                        st1_data *= factor_conver_psc * 100
                        st3_data *= factor_conver_psc * 100
                        st5_data *= factor_conver_psc * 100
                except AttributeError:
                    print("")

                max_abs_a_value = max(np.max(st1_data), np.min(st1_data), key=abs)
                pga_a_value = max_abs_a_value

                max_abs_v_value = max(np.max(st3_data), np.min(st3_data), key=abs)
                pga_v_value = max_abs_v_value

                max_abs_d_value = max(np.max(st5_data), np.min(st5_data), key=abs)
                pga_d_value = max_abs_d_value

                # data_vel = np.round(st3.data * station.stats.calib * (1 / f_calib), 4) if f_calib else np.round(st3.data * station.stats.calib, 4)
                # data_dsp = np.round(st5.data * station.stats.calib * (1 / f_calib), 4) if f_calib else np.round(st5.data * station.stats.calib, 4)

                seismic_record_instance = TraceData(
                    trace_a_unit=cuv1,
                    traces_a=st1_data.tolist(),
                    peak_a=pga_a_value,
                    trace_v_unit=cuv2,
                    traces_v=st3_data.tolist(),
                    peak_v=pga_v_value,
                    trace_d_unit=cuv3,
                    traces_d=st5_data.tolist(),
                    peak_d=pga_d_value,
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

# ----------------------------------------------------------------------

class ConvertionDataView(viewsets.ModelViewSet):
    queryset = TraceData.objects.all()
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
        zero_ph = request.data.get('zero', False)
        t_min = request.data.get('t_min')
        t_max = request.data.get('t_max')
        #convert_value = request.data.get('unit', '')
        convert_from_unit = request.data.get('unit_from', '')
        convert_to_unit = request.data.get('unit_to', '')
        
        if not data_str:
            return Response({'message': 'No se proporcionaron datos suficientes para la lectura'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if data_str:
                sts  = obspy.read(data_str)
                sts.merge(method=1, fill_value= 'latest')
                inventory = self.read_inventory_safe(data_str)
                if baseline_type:
                    sts.detrend(type=baseline_type)
                if t_min and t_max:
                    min_time = obspy.UTCDateTime(t_min)
                    max_time = obspy.UTCDateTime(t_max)
                    sts.trim(min_time,max_time)
                    
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        saved_instances = []

        f_calib = None
        if inventory:
            sts.attach_response(inventory)
            sts.remove_sensitivity()

        for station in sts:
            if (station.stats.station == station_data and station.stats.channel == channel_data):

                indice_traza = 0

                for i, traza in enumerate(sts):
                    if traza.stats.channel == station.stats.channel:
                        indice_traza = i
                        break
                    
                sampling = station.stats.sampling_rate
                tiempo = np.round(np.arange(0, station.stats.npts / sampling, station.stats.delta), 4)

                st1 = station.copy()

                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st1.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)

                st2 = st1.copy()
                st3 = st2.integrate(method='cumtrapz')
                
                if baseline_type:
                   st3.detrend(type=baseline_type)

                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st3.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)
                
                # if filter_type == 'bandpass' or filter_type == 'bandstop' :
                #     st3.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=True)

                st4 = st3.copy()
                st5 = st4.integrate(method='cumtrapz')
                if baseline_type:
                   st5.detrend(type=baseline_type)

                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st5.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)
                # if filter_type == 'bandpass' or filter_type == 'bandstop' :
                #     st5.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=True)
                
                # conversion_factors = {
                #     'g': 0.00101972,
                #     'm': 0.01,
                #     'gal': 1,
                #     '': 1
                # }

                # conversion_factor = conversion_factors.get(convert_unit, 1)

                # if convert_unit == 'g':
                #     st1_data = st1.data * station.stats.calib * conversion_factor * 100
                #     st3_data = st3.data * station.stats.calib * 100
                #     st5_data = st5.data * station.stats.calib * 100
                #     cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                # else:
                #     st1_data = st1.data * station.stats.calib * conversion_factor * 100
                #     st3_data = st3.data * station.stats.calib * conversion_factor * 100
                #     st5_data = st5.data * station.stats.calib * conversion_factor * 100
                #     if convert_unit == 'm':
                #         cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                #     elif convert_unit == 'gal':
                #         cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                #     else:
                #         cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                filename = data_str.split('/')[-1]
                extension = splitext(filename)[1]

                if convert_from_unit:
                    if convert_from_unit == 'gal':
                        if convert_to_unit == 'm':
                            st1_data = st1.data * station.stats.calib * 0.01
                            st3_data = st3.data * station.stats.calib * 0.01
                            st5_data = st5.data * station.stats.calib * 0.01
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'gal' or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'g':
                            st1_data = st1.data * station.stats.calib * 0.001019
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                    if convert_from_unit == 'm':
                        if convert_to_unit == 'gal':
                            st1_data = st1.data * station.stats.calib * 100
                            st3_data = st3.data * station.stats.calib * 100
                            st5_data = st5.data * station.stats.calib * 100
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'm'  or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'g':
                            st1_data = st1.data * station.stats.calib * 0.101972
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                    if convert_from_unit == 'g':
                        if convert_to_unit == 'gal':
                            st1_data = st1.data * station.stats.calib * 980.66
                            st3_data = st3.data * station.stats.calib * 100
                            st5_data = st5.data * station.stats.calib * 100
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                        if convert_to_unit == 'm':
                            st1_data = st1.data * station.stats.calib * 9.8066
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                        if convert_to_unit == 'g' or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'unk', 'unk'
                    if convert_from_unit == '' or convert_from_unit == 'null':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'unk', 'unk', 'unk'
                else:
                    st1_data = st1.data * station.stats.calib * 1
                    st3_data = st3.data * station.stats.calib * 1
                    st5_data = st5.data * station.stats.calib * 1
                    cuv1, cuv2, cuv3 = '-unk', '-unk', '-unk'
                
                if extension == '.evt':
                    st1_data *= 100 
                    st3_data *= 100
                    st5_data *= 100

                try:
                    if station.stats.reftek130:
                        tbw = float(station.stats.reftek130.channel_true_bit_weights[indice_traza].split()[0])
                        ch_gain = float(station.stats.reftek130.channel_gain_code[indice_traza])
                        vpu = station.stats.reftek130.channel_sensor_vpu[indice_traza]
                        factor_conver_psc = 1/ (ch_gain*vpu*1000000/(tbw*9.81))
                        st1_data *= factor_conver_psc * 100
                        st3_data *= factor_conver_psc * 100
                        st5_data *= factor_conver_psc * 100

                except AttributeError:
                    print("")

                max_abs_a_value = max(np.max(st1_data), np.min(st1_data), key=abs)
                pga_a_value = max_abs_a_value

                max_abs_v_value = max(np.max(st3_data), np.min(st3_data), key=abs)
                pga_v_value = max_abs_v_value

                max_abs_d_value = max(np.max(st5_data), np.min(st5_data), key=abs)
                pga_d_value = max_abs_d_value

                # data_vel = np.round(st3.data * station.stats.calib * (1 / f_calib), 4) if f_calib else np.round(st3.data * station.stats.calib, 4)
                # data_dsp = np.round(st5.data * station.stats.calib * (1 / f_calib), 4) if f_calib else np.round(st5.data * station.stats.calib, 4)
                

                seismic_record_instance = TraceData(
                    trace_a_unit=cuv1,
                    traces_a=st1_data.tolist(),
                    peak_a=pga_a_value,
                    trace_v_unit=cuv2,
                    traces_v=st3_data.tolist(),
                    peak_v=pga_v_value,
                    trace_d_unit=cuv3,
                    traces_d=st5_data.tolist(),
                    peak_d=pga_d_value,
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

class ConvertToStream(viewsets.ModelViewSet):
    queryset = UploadFile.objects.all()
    serializer_class = FileUploadSerializer

    def create(self, request, *args, **kwargs):
        data = request.data.get('data')

        if data is not None:
            data_array = [data]
            stream = Stream()

            trace_data_dict = {}
            delta_calculated = False
            calibs = 1
            unit = ''

            for f in data_array:
                delta = f['delta']
                net = f['network']
                sta = f['station']
                loca = f['location']
                unit = f['unidad']

                for key, value in f.items():
                    if key.startswith('c_'):
                        channel_number = key[2:]  
                        if channel_number not in trace_data_dict:
                            trace_data_dict[channel_number] = {'data': [], 'channel': ''}

                        if value != 'T':  
                            trace_data_dict[channel_number]['data'].append(value) 

                    elif key.startswith('cc_'):
                        channel_number = key[3:]  
                        if channel_number in trace_data_dict:
                            trace_data_dict[channel_number]['channel'] = value  

                        
                        if value == 'T' and not delta_calculated:
                            data_time = f['c_' + channel_number]  
                            delta = data_time[1] - data_time[0] 
                            delta_calculated = True

            
            for channel_number, data_info in trace_data_dict.items():
               
                if data_info['channel'] != 'T':
                    array_np = np.array(data_info['data'], dtype=np.float64)
                    array_np = array_np.flatten()

                    trace = Trace(data=array_np, header={
                        'network': net,
                        'station': sta,
                        'location': loca,
                        'delta': delta,
                    })
                    trace.stats.channel = data_info['channel']
                    stream.append(trace)
           
            unique_filename =  f"{uuid.uuid4().hex}.mseed"
 
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                stream.write(temp_file.name, format="MSEED")

                nuevo_archivo = UploadFile()
                nuevo_archivo.file.save(unique_filename, temp_file)
                nuevo_archivo.save()

                serializer = FileUploadSerializer(nuevo_archivo)

            os.unlink(temp_file.name)

            file_url = request.build_absolute_uri(serializer.data['file'])

            return Response({'url':file_url}, status=status.HTTP_201_CREATED)
        else:
            return Response({'error': 'No se proporcionaron datos de stream'}, status=status.HTTP_400_BAD_REQUEST)
        
class AutoAdjustView(viewsets.ModelViewSet):
    queryset = TraceData.objects.all()
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
        zero_ph = request.data.get('zero', False)
        convert_from_unit = request.data.get('unit_from', '')

        if not data_str:
            return Response({'message': 'No se proporcionaron datos suficientes para la lectura'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if data_str:

                baseline_type = 'linear'
                filter_type = 'bandpass'
                freq_min = 0.1
                freq_max = 25
                corner = 2
                zero_ph = True
                convert_to_unit = 'gal'

                sts = obspy.read(data_str)
                sts.merge(method=1, fill_value= 'latest')
                inventory = self.read_inventory_safe(data_str)

                sts.detrend(type=baseline_type)
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        saved_instances = []

        f_calib = None

        if inventory:
            sts.attach_response(inventory)
            sts.remove_sensitivity()

        for station in sts:
            if (station.stats.station == station_data and station.stats.channel == channel_data):
                
                indice_traza = 0
                formato_file = station.stats._format

                for i, traza in enumerate(sts):
                    if traza.stats.channel == station.stats.channel:
                        indice_traza = i
                        break

                sampling = station.stats.sampling_rate
                tiempo = np.round(np.arange(0, station.stats.npts / sampling, station.stats.delta), 4)

                st1 = station.copy()

                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st1.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)

                st2 = st1.copy()
                st3 = st2.integrate(method='cumtrapz')

                if baseline_type:
                   st3.detrend(type=baseline_type)

                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st3.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)
                

                st4 = st3.copy()
                st5 = st4.integrate(method='cumtrapz')
                
                if baseline_type:
                   st5.detrend(type=baseline_type)

                if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    if type(zero_ph) == str and zero_ph =='true':
                        zph = True
                    elif type(zero_ph) == str and zero_ph =='false':
                        zph = False
                    else:
                        zph = bool(zero_ph) 

                    st5.filter(str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=zph)
                
                filename = data_str.split('/')[-1]
                extension = splitext(filename)[1]

                if convert_from_unit:
                    if convert_from_unit == 'gal':
                        if convert_to_unit == 'm':
                            st1_data = st1.data * station.stats.calib * 0.01
                            st3_data = st3.data * station.stats.calib * 0.01
                            st5_data = st5.data * station.stats.calib * 0.01
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'gal' or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'g':
                            st1_data = st1.data * station.stats.calib * 0.001019
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                    if convert_from_unit == 'm':
                        if convert_to_unit == 'gal':
                            st1_data = st1.data * station.stats.calib * 100
                            st3_data = st3.data * station.stats.calib * 100
                            st5_data = st5.data * station.stats.calib * 100
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'm'  or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'g':
                            st1_data = st1.data * station.stats.calib * 0.101972
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                    if convert_from_unit == 'g':
                        if convert_to_unit == 'gal':
                            st1_data = st1.data * station.stats.calib * 980.66
                            st3_data = st3.data * station.stats.calib * 100
                            st5_data = st5.data * station.stats.calib * 100
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                        if convert_to_unit == 'm':
                            st1_data = st1.data * station.stats.calib * 9.8066
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                        if convert_to_unit == 'g' or convert_to_unit == '':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'unk', 'unk'
                    if convert_from_unit == '' or convert_from_unit == 'null':
                            st1_data = st1.data * station.stats.calib * 1
                            st3_data = st3.data * station.stats.calib * 1
                            st5_data = st5.data * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'unk', 'unk', 'unk'
                else:
                    st1_data = st1.data * station.stats.calib * 1
                    st3_data = st3.data * station.stats.calib * 1
                    st5_data = st5.data * station.stats.calib * 1
                    cuv1, cuv2, cuv3 = '-unk', '-unk', '-unk'
                
                if extension == '.evt':
                    st1_data *= 100 
                    st3_data *= 100
                    st5_data *= 100

                try:
                    if station.stats.reftek130:
                        tbw = float(station.stats.reftek130.channel_true_bit_weights[indice_traza].split()[0])
                        ch_gain = float(station.stats.reftek130.channel_gain_code[indice_traza])
                        vpu = station.stats.reftek130.channel_sensor_vpu[indice_traza]
                        factor_conver_psc = 1/ (ch_gain*vpu*1000000/(tbw*9.81))
                        st1_data *= factor_conver_psc * 100
                        st3_data *= factor_conver_psc * 100
                        st5_data *= factor_conver_psc * 100
                except AttributeError:
                    print("")

                max_abs_a_value = max(np.max(st1_data), np.min(st1_data), key=abs)
                pga_a_value = max_abs_a_value

                max_abs_v_value = max(np.max(st3_data), np.min(st3_data), key=abs)
                pga_v_value = max_abs_v_value

                max_abs_d_value = max(np.max(st5_data), np.min(st5_data), key=abs)
                pga_d_value = max_abs_d_value

                # data_vel = np.round(st3.data * station.stats.calib * (1 / f_calib), 4) if f_calib else np.round(st3.data * station.stats.calib, 4)
                # data_dsp = np.round(st5.data * station.stats.calib * (1 / f_calib), 4) if f_calib else np.round(st5.data * station.stats.calib, 4)

                seismic_record_instance = TraceData(
                    formato = formato_file,
                    trace_a_unit=cuv1,
                    traces_a=st1_data.tolist(),
                    peak_a=pga_a_value,
                    trace_v_unit=cuv2,
                    traces_v=st3_data.tolist(),
                    peak_v=pga_v_value,
                    trace_d_unit=cuv3,
                    traces_d=st5_data.tolist(),
                    peak_d=pga_d_value,
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

# ------------------------------------------------------------------------

class TestSendData(viewsets.ModelViewSet):
    queryset = TraceData.objects.all()
    serializer_class = TraceDataSerializer

    def create(self, request, *args, **kwargs):
        trace_data = request.data.get('trace_data')
        trace_time = request.data.get('trace_time')
        start_time = request.data.get('start_time')
        baseline_type = request.data.get('base_line' , '')
        filter_type = request.data.get('filter_type', '')
        freq_min = request.data.get('freq_min', '')
        freq_max = request.data.get('freq_max', '')
        corner = request.data.get('corner', '')
        t_min = request.data.get('t_min')
        t_max = request.data.get('t_max')
        convert_unit = request.data.get('unit', '')

        if trace_data is not None:
            
            st = Stream()

            tiempo_a = np.array(trace_time)

            starttime = UTCDateTime(start_time)
            endtime = starttime + len(trace_data)

            trz = np.array(trace_data)
            
            trace = Trace(data=trz, header={
               'starttime': starttime,
               'endtime': endtime,
            })
            trc_st = Stream([trace])
            st += trc_st

            saved_instances = []

            if baseline_type:
                    st.detrend(type=baseline_type)

            if t_min and t_max:
                    min_time = obspy.UTCDateTime(t_min)
                    max_time = obspy.UTCDateTime(t_max)
                    st.trim(min_time,max_time)

            if filter_type == 'bandpass' or filter_type == 'bandstop' :
                    st.filter(trace, str(filter_type), freqmin=float(freq_min), freqmax=float(freq_max), corners=float(corner), zerophase=True)
            
           
            st2 = st.copy()
            st3 = st2.integrate(method='cumtrapz')

            st4 = st3.copy()
            st5 = st4.integrate(method='cumtrapz')

            conversion_factors = {
                    'g': 0.00101972,
                    'm': 0.01,
                    'gal': 100,
                    '': 100
                }
                
            conversion_factor = conversion_factors.get(convert_unit, 1)

            st1_data =  st[0].data * conversion_factor
            st3_data = st3[0].data * conversion_factor
            st5_data = st5[0].data * conversion_factor

            max_abs_a_value = max(np.max(st1_data), np.min(st1_data), key=abs)
            pga_a_value = max_abs_a_value

            max_abs_v_value = max(np.max(st3_data), np.min(st3_data), key=abs)
            pga_v_value = max_abs_v_value

            max_abs_d_value = max(np.max(st5_data), np.min(st5_data), key=abs)
            pga_d_value = max_abs_d_value

            seismic_record_instance = TraceData(
                traces_a=st1_data.tolist(),
                peak_a=pga_a_value,
                traces_v=st3_data.tolist(),
                peak_v=pga_v_value,
                traces_d=st5_data.tolist(),
                peak_d=pga_d_value,
                tiempo_a=tiempo_a.tolist()
            )
            
            saved_instances.append(seismic_record_instance)

            serializer = self.get_serializer(saved_instances, many=True)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response({'error': 'No se proporcionaron datos de stream'}, status=status.HTTP_400_BAD_REQUEST)

# -------------------------------------------------------------------

class ProyectoView(viewsets.ModelViewSet):
    queryset = Proyecto.objects.all()
    serializer_class = ProyectoSerializer

    def create(self, request, *args, **kwargs):
        serializer = ProyectoSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    


class getProyectoView(viewsets.ModelViewSet):
    queryset = Proyecto.objects.all()
    serializer_class = ProyectoSerializer

    def buscar_proyecto(self, request, uuid):
        proyectos = Proyecto.objects.filter(uuid=uuid)
        if not proyectos:
            raise NotFound(detail="Proyecto no encontrado")
        serializer = ProyectoSerializer(proyectos, many=True)
        return Response(serializer.data)

# ---------------------------------------------------------------------

class getUserProjectsView(viewsets.ModelViewSet):
    queryset = Proyecto.objects.all()
    serializer_class = ProyectoSerializer

    def buscar_user_proyecto(self, request, uuid):
        try:
            proyectos = Proyecto.objects.filter(user=uuid)
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)    
        serializer = self.get_serializer(proyectos, many=True)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

class FilesViewSet(viewsets.ModelViewSet):
    queryset = Files.objects.all()
    serializer_class = FilesSerializer

    def create(self, request, *args, **kwargs):
        proyecto_id = request.data.get('proyecto', None) 

        if proyecto_id is not None:
            try:
                proyecto = Proyecto.objects.get(pk=proyecto_id) 
            except Proyecto.DoesNotExist:
                return Response({'error': 'El proyecto no existe.'}, status=status.HTTP_400_BAD_REQUEST)

            request.data['proyecto'] = proyecto.id

            return super().create(request, *args, **kwargs)
        else:
            return Response({'error': 'La ID del proyecto es necesaria.'}, status=status.HTTP_400_BAD_REQUEST)

class FileInfoViewSet(viewsets.ModelViewSet):
    queryset = FileInfo.objects.all()
    serializer_class = FileInfoSerializer

    def create(self, request, *args, **kwargs):
        file_id = request.data.get('files', None)

        if file_id is not None:
            try:
                file = Files.objects.get(pk=file_id)
            except Files.DoesNotExist:
                return Response({'error': 'El File no existe.'}, status=status.HTTP_400_BAD_REQUEST)

            request.data['files'] = file.id

            return super().create(request, *args, **kwargs)
        else:
            return Response({'error': 'La ID del File es necesaria.'}, status=status.HTTP_400_BAD_REQUEST)

class StationInfoViewSet(viewsets.ModelViewSet):
    queryset = StationInfo.objects.all()
    serializer_class = StationInfoSerializer

    def create(self, request, *args, **kwargs):
        fileInfo_id = request.data.get('fileInfo', None)
        trace_id = request.data.get('trace', None)

        if fileInfo_id is not None and trace_id is not None:
            try:
                fileInfo = FileInfo.objects.get(pk=fileInfo_id)
                trace = Traces.objects.get(pk=trace_id)

            except (FileInfo.DoesNotExist, Traces.DoesNotExist):  
                return Response({'error': 'El File o la traza no existe.'}, status=status.HTTP_400_BAD_REQUEST)

            request.data['fileInfo'] = fileInfo.id
            request.data['trace'] = trace.id

            return super().create(request, *args, **kwargs)
        else:
            return Response({'error': 'La ID del File y la traza son necesarias.'}, status=status.HTTP_400_BAD_REQUEST)

# -----------------------------------------------------------------------

class RegisterUserListView(viewsets.ModelViewSet):
    queryset = RegisterUser.objects.all()
    serializer_class = RegisterUserPSerializer

class ProyectoListView(viewsets.ModelViewSet):
    queryset = Proyecto.objects.all()
    serializer_class = ProyectoPSerializer

class FilesListViewSet(viewsets.ModelViewSet):
    queryset = Files.objects.all()
    serializer_class = FilesPSerializer

class FileInfoListViewSet(viewsets.ModelViewSet):
    queryset = FileInfo.objects.all()
    serializer_class = FileInfoPSerializer

class StationInfoListViewSet(viewsets.ModelViewSet):
    queryset = StationInfo.objects.all()
    serializer_class = StationInfoPSerializer

class TracesListViewSet(viewsets.ModelViewSet):
    queryset = Traces.objects.all()
    serializer_class = TracesSerializer


def options_view(request):
    response = HttpResponse()
    response['Allow'] = "GET, POST, OPTIONS"
    return response

@api_view(['GET', 'POST'])
def xmr_txt(request):
    if request.method == 'GET':
        return Response({'data': 'D'}, status=status.HTTP_201_CREATED)
    elif request.method == 'POST':
        name_file = request.data.get('name_file', '')
        try:
            result = subprocess.check_output(name_file, shell=True, stderr=subprocess.STDOUT)
            return Response({'output': f'{result}'}, status=status.HTTP_200_OK)
        except subprocess.CalledProcessError as e:
            return Response({'error': e.output.decode('utf-8')}, status=status.HTTP_400_BAD_REQUEST)
        


@api_view(['GET', 'POST'])
def snippet_list(request):

    if request.method == 'GET':
        proy_s = Proyecto.objects.all()
        usertid = request.GET.get('user', None)

        if usertid:
            proy_s = proy_s.filter(user=usertid)
        
        serializer = ProyectoSerializer(proy_s, many=True)
        data = []
        
        for proyecto in serializer.data:
            proyecto_id = proyecto['id']
            files = Files.objects.filter(proyecto=proyecto_id)
            files_serializer = FilesSerializer(files, many=True)
            data.append({
                "proyecto": proyecto,
                "files": files_serializer.data
            })

        return Response(data)

    elif request.method == 'POST':
        serializer = ProyectoPSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'POST'])
def mseed_xml(request):

    if request.method == 'GET':       
       dd = ''
       return Response({'data': 'D'}, status=status.HTTP_201_CREATED)
    
    elif request.method == 'POST':

        mseed_file = request.data.get('mseed_file', '')
        xml_file   = request.data.get('xml_file', '')
        test = request.data.get('calib_factor', '')
        calib_unit = request.data.get('calib_unit', '')

        if test and mseed_file:
            sta_mseed = obspy.read(mseed_file)
            sta_mseed.merge(method=1)
            stream = Stream()

            
            for i, trace in enumerate(sta_mseed):
                factor_key = f'c_{i}'  
                factor = test.get(factor_key, 1)  
                # Ensure trace.data is of a compatible dtype, such as float64
                trace.data = trace.data.astype(np.float64)  
                trace.data *= factor

            unique_filename =  f"{uuid.uuid4().hex}.mseed"
 
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                sta_mseed.write(temp_file.name, format="MSEED")

                nuevo_archivo = UploadFile()
                nuevo_archivo.file.save(unique_filename, temp_file)
                nuevo_archivo.save()

                serializer = FileUploadSerializer(nuevo_archivo)

            os.unlink(temp_file.name)

            file_url = request.build_absolute_uri(serializer.data['file'])

            return Response({'url':file_url}, status=status.HTTP_201_CREATED)
        
        elif mseed_file and xml_file:

            sta_mseed = obspy.read(mseed_file)
            
            sta_xml = obspy.read_inventory(xml_file)

            for net in sta_xml:
                for sta in net:
                    if(sta.code == sta_mseed[0].stats.station):
                        for cha in sta:
                            unit_found = cha.response.instrument_sensitivity.input_units
            
            if unit_found == 'M/S**2':
                unit = 'm'
            elif unit_found == 'CM/S**2':
                unit= 'cm'
            elif unit_found == 'G':
                unit= 'cm'
            else:
                unit = ''

            sta_invSta = sta_xml.select(station=sta_mseed[0].stats.station)
            sta_mseed.attach_response(sta_invSta)
            sta_mseed.remove_sensitivity()

            unique_filename =  f"{uuid.uuid4().hex}.mseed"
 
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                sta_mseed.write(temp_file.name, format="MSEED")

                nuevo_archivo = UploadFile()
                nuevo_archivo.file.save(unique_filename, temp_file)
                nuevo_archivo.save()

                serializer = FileUploadSerializer(nuevo_archivo)

            os.unlink(temp_file.name)

            file_url = request.build_absolute_uri(serializer.data['file'])

            return Response({'url':file_url, 'unit': unit}, status=status.HTTP_201_CREATED)
        else:
            return Response({"error" : 'No se proporcio los datos'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'POST'])
def create_fourier(request):
      if request.method == 'GET':
       
       dd = ''
      elif request.method == 'POST':
        data_str = request.data.get('data', '')
        station_data = request.data.get('station_selected')
        channel_data = request.data.get('channel_selected')

        if not data_str:
             raise APIException('No se proporcionó datos para Lectura')
        try:
            st = obspy.read(data_str) 
            inventory = None
            try:
                inventory = obspy.read_inventory(data_str)
                if inventory:
                    st.attach_response(inventory)
                    st.remove_sensitivity()
            except Exception as inventory_error:
                print(f'')

        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        
        for station in st:
            if (station.stats.station == station_data and station.stats.channel == channel_data):

                station.detrend('linear')
                station.filter('bandpass', freqmin=0.1,freqmax=25, corners=2, zerophase=True)

                four = station.data
                four = 10000 * four

                fps = station.stats.sampling_rate
                N = four.size
                T = 1.0/fps
                band = 1.0/(2.0*T)
                yf1 = np.fft.fft(four)
                yo1 = np.abs(yf1[0:int(N/2)])
                xf = np.linspace(0.0, band, int(N/2))

                epsilon = 1e-10
                xf_nonzero = np.where(xf > epsilon, xf, epsilon)
                periods = 1.0 / xf_nonzero
                smoothed_signal = convolve(yo1, Box1DKernel(80))

                min_period = 0.01
                max_period = 10.0

                mask = (periods >= min_period) & (periods <= max_period)

                per = periods[mask]
                amp = (2.0/N)*smoothed_signal[mask]

        return Response({'periodo': per, "amplitud": amp}, status=status.HTTP_201_CREATED)

@api_view(['GET', 'POST'])
def create_espectro(request):
      if request.method == 'GET':
       
       dd = ''
      elif request.method == 'POST':
        data_str = request.data.get('data', '')
        station_data = request.data.get('station_selected')
        channel_data = request.data.get('channel_selected')

        if not data_str:
             raise APIException('No se proporcionó datos para Lectura')
        try:
            st = obspy.read(data_str) 
            inventory = None
            try:
                inventory = obspy.read_inventory(data_str)
                if inventory:
                    st.attach_response(inventory)
                    st.remove_sensitivity()
            except Exception as inventory_error:
                print(f'')

        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        
        for station in st:
            if (station.stats.station == station_data and station.stats.channel == channel_data):
                
                osc_damping = 0.05
                station.detrend('linear')
                station.filter('bandpass', freqmin=0.1,freqmax=25, corners=2, zerophase=True)

                fps = station.stats.sampling_rate
                T = 1.0/fps
                four = station.data
                accels = (100000.0/980.0) * four

                escalax = np.logspace(-2,1,100)

                osc_freqs = 1.0/escalax
                res_spec = pyrotd.calc_spec_accels(T, accels, osc_freqs, osc_damping)


        return Response({'periodo': escalax, "amplitud": res_spec.spec_accel}, status=status.HTTP_201_CREATED)