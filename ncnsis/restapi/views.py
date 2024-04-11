

from posixpath import splitext
import subprocess
import tempfile
from django.conf import settings
from .models import *
from restapi.serializers import *

from django.core.validators import validate_email
from django.contrib.auth.models import Group, User
from django.contrib.auth import logout
from django.http import HttpResponse

from rest_framework import permissions, viewsets, authentication, status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, APIException, ValidationError
from rest_framework.decorators import action, api_view 


import obspy
import os
import uuid
import pyrotd
import validators

from obspy import Stream, Trace, UTCDateTime, read_inventory
from astropy.convolution import convolve, Gaussian1DKernel, Box1DKernel

from datetime import datetime

import numpy as np

import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import matplotlib.image as mpimg


# class CustomAuthToken(ObtainAuthToken):

#     def post(self, request, *args, **kwargs):
#         serializer = self.serializer_class(data=request.data,
#                                            context={'request': request})
#         serializer.is_valid(raise_exception=True)
#         user = serializer.validated_data['user']
#         token, created = Token.objects.get_or_create(user=user)
#         return Response({
#             'token': token.key,
#             'user_id': user.pk,
#             'email': user.email
#         })

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

@api_view(['GET', 'POST'])
def station_data(request):
    
    if request.method == 'GET':       
       dd = ''
    elif request.method == 'POST':
        data_str = request.data.get('data')

        if not data_str:
            return Response({'error': 'No se proporcionó datos para Lectura'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            sts = obspy.read(data_str)
            sts.merge(method=1, fill_value= 'latest')
            tr_info = extract_tr_info(sts)
            inventory = read_inventory_safe(data_str)
            combined_info = combine_tr_and_inv_info(tr_info, inventory)
            #seismic_record_instance = SeismicData(data=combined_info)            
            return Response({'data' : combined_info}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
def upload_file(request):
    
    if request.method == 'POST':
        if 'file' in request.FILES:
            uploaded_file = request.FILES['file']
        else:
            uploaded_file = None

        data_str = request.data.get('string_data', '')
        user_ip = request.data.get('info', '')
        format_file = ''

        try:
            if uploaded_file:
                file = UploadFile(file=uploaded_file, ip=user_ip)
                file.save()
                serializer = FileUploadSerializer(file)
                file_url = request.build_absolute_uri(serializer.data['file'])

                filename = file_url.split('/')[-1]
                extension = splitext(filename)[1]

                try:
                    if extension == '.txt':
                        format_file = 'TXT'
                    elif extension == '.xml':
                        format_file = 'XML'
                    else :
                        st = obspy.read(file_url)
                        format_file = st[0].stats._format
                except:
                    format_file = ''
                    # os.remove(os.path.join(settings.MEDIA_ROOT, serializer.data['file'] ))
                    # file.delete()
                    return Response({'error': 'Formato no valido'}, status=status.HTTP_406_NOT_ACCEPTABLE)
                return Response({
                    'file': file_url,
                    'string_data': None,
                    'f' : format_file
                    }, status=status.HTTP_201_CREATED)
            elif data_str:
                if validators.url(data_str):
                    url = UploadFile(string_data=data_str, ip=user_ip)
                    url.save()
                    serializer = FileUploadSerializer(url)
                    string_url = request.build_absolute_uri(serializer.data['string_data'])

                    filename  = string_url.split('/')[-1]
                    extension = splitext(filename)[1]

                    try:
                        if extension == '.txt':
                            format_file = 'TXT'
                        elif extension == '.xml':
                            format_file = 'XML'
                        else :
                            st = obspy.read(string_url)
                            format_file = st[0].stats._format
                    except:
                        format_file = ''
                        # os.remove(os.path.join(settings.MEDIA_ROOT, serializer.data['file'] ))
                        # url.delete()
                        return Response({'error': 'Formato no valido'}, status=status.HTTP_406_NOT_ACCEPTABLE)
                    return Response({
                        'file': None,
                        'string_data': string_url,
                        'f' : format_file
                        }, status=status.HTTP_201_CREATED)
                else:
                    raise ValidationError('No es Valido')                     
            else:
                raise ValidationError('No se proporcionaron datos')
        except Exception as e:
            return Response({'error': 'Verificar Datos, no son Validos'}, status=status.HTTP_400_BAD_REQUEST)
        
@api_view(['GET', 'POST'])
def data_plot(request):
    if request.method == 'GET':       
       dd = ''
    elif request.method == 'POST':
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

        graph_color = request.data.get('graph_color', 'b')

        if not data_str:
            raise APIException('No se proporcionó datos para Lectura')
        try:
            sts = obspy.read(data_str)
            sts.merge(method=1, fill_value= 'latest')
            inventory = read_inventory_safe(data_str)

            if t_min and t_max:
                min_time = obspy.UTCDateTime(t_min)
                max_time = obspy.UTCDateTime(t_max)
                sts.trim(min_time,max_time)

            if baseline_type:
                sts.detrend(type=baseline_type)

            unit_found = ''
            saved_instances = []
            station_full_name = ''

            if inventory:
                for net in inventory:
                    for sta in net:
                        if(sta.code == station_data):
                            for cha in sta:
                                unit_found = cha.response.instrument_sensitivity.input_units    

                sts.attach_response(inventory)            
                sts.remove_sensitivity()

            for station in sts:
                try:
                    if station.stats.kinemetrics_evt.chan_id == channel_data:
                        channel_data = station.stats.channel
                        station_full_name = f'{station.stats.network}.{station.stats.station}.{station.stats.location}.{station.stats.kinemetrics_evt.chan_id}'
                except:
                    channel_data = channel_data
                    station_full_name = f'{station.stats.network}.{station.stats.station}.{station.stats.location}.{station.stats.channel}'


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
                            if convert_to_unit == 'mg':
                                st1_data = st1.data * station.stats.calib * 1.020
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'mg', 'cm/s', 'cm'
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
                                st1_data = st1.data * station.stats.calib * 0.102
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                            if convert_to_unit == 'mg':
                                st1_data = st1.data * station.stats.calib * 102.04
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'mG', 'm/s', 'm'
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
                                cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                            if convert_to_unit == 'mg':
                                st1_data = st1.data * station.stats.calib * 1000
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'mg', 'm/s', 'm'
                        if convert_from_unit == 'mg':
                            if convert_to_unit == 'm':
                                st1_data = st1.data * station.stats.calib * 0.0098
                                st3_data = st3.data * station.stats.calib * 0.0098
                                st5_data = st5.data * station.stats.calib * 0.0098
                                cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                            if convert_to_unit == 'gal':
                                st1_data = st1.data * station.stats.calib * 0.980
                                st3_data = st3.data * station.stats.calib * 0.980
                                st5_data = st5.data * station.stats.calib * 0.980
                                cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                            if convert_to_unit == 'g':
                                st1_data = st1.data * station.stats.calib * 0.001
                                st3_data = st3.data * station.stats.calib * 0.981
                                st5_data = st5.data * station.stats.calib * 0.981
                                cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                            if convert_to_unit == 'mg'  or convert_to_unit == '':
                                st1_data = st1.data * station.stats.calib * 1
                                st3_data = st3.data * station.stats.calib * 0.980
                                st5_data = st5.data * station.stats.calib * 0.980
                                cuv1, cuv2, cuv3 = 'mg', 'cm/s', 'cm'
                        if convert_from_unit == '' or convert_from_unit == 'null':
                                st1_data = st1.data * station.stats.calib * 1
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'unk', 'unk', 'unk'
                        
                    else:
                        st1_data = st1.data * station.stats.calib * 1
                        st3_data = st3.data * station.stats.calib * 1
                        st5_data = st5.data * station.stats.calib * 1
                        cuv1, cuv2, cuv3 = '-unk-', '-unk-', '-unk-'

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
                    pga_a_value = format_value(max_abs_a_value)

                    max_abs_v_value = max(np.max(st3_data), np.min(st3_data), key=abs)
                    pga_v_value = format_value(max_abs_v_value)

                    max_abs_d_value = max(np.max(st5_data), np.min(st5_data), key=abs)
                    pga_d_value = format_value(max_abs_d_value) 

                    utc = 0

                    fig = plt.figure(figsize=(10,8))
                    try: 
                        marca_de_agua = mpimg.imread('/var/www/apiqs.ncn.pe/ncnsis/static/ncnLogoColor.png')
                    except:
                        marca_de_agua = mpimg.imread('static/ncnLogoColor.png')

                    fig.figimage(marca_de_agua, 300, 200, alpha=0.09)

                    ax = fig.add_subplot(311)
                    ttac2 = str(UTCDateTime(station.stats.starttime) ).split("T")
                    titulo_hora  = "Fecha: " + ttac2[0] + " / Hora: " + ttac2[1][0:8] + " UTC " + str(utc)

                    ax.set_title(station.stats.network +'.' + station.stats.station + '.'+ station.stats.location +' / ' + str(titulo_hora) )

                    sy = st1_data
                    st = station_full_name
                    ax.text(0.01, 0.95, st ,verticalalignment='top', horizontalalignment='left',transform=ax.transAxes,color='k', fontsize=10)
                    ax.text(0.81, 0.95,'PGA: '+str(pga_a_value)+f' {cuv1}',horizontalalignment='left',verticalalignment='top',transform = ax.transAxes)
                    plt.plot(tiempo, sy,graph_color,linewidth=0.3)
                    plt.ylabel(f'Aceleracion [{cuv1}]')
                    plt.grid()

                    ax1 = fig.add_subplot(312, sharex=ax)
                    sy1 = st3_data
                    st1 = station_full_name
                    ax1.text(0.01, 0.95,st1,verticalalignment='top', horizontalalignment='left',transform=ax1.transAxes,color='k', fontsize=10)
                    ax1.text(0.81, 0.95,'PGV: '+str(pga_v_value)+ f' {cuv2}',horizontalalignment='left',verticalalignment='top',transform = ax1.transAxes)
                    plt.plot(tiempo, sy1,graph_color,linewidth=0.3)
                    plt.ylabel(f'Velocidad [{cuv2}]')
                    plt.grid()

                    ax2 = fig.add_subplot(313, sharex=ax)
                    sy2 = st5_data
                    st2 = station_full_name
                    ax2.text(0.01, 0.95,st2,verticalalignment='top', horizontalalignment='left',transform=ax2.transAxes,color='k', fontsize=10)
                    ax2.text(0.81, 0.95,'PGD: '+str(pga_d_value)+f' {cuv3}',horizontalalignment='left',verticalalignment='top',transform = ax2.transAxes)
                    plt.plot(tiempo, sy2,graph_color,linewidth=0.3)
                    plt.ylabel(f'Desplazamiento [{cuv3}]')
                    plt.grid()
                  
                    current_datetime = datetime.now().strftime('%Y%m%d_%H%M%S')

                    image_filename = f'{station.stats.station}_{station.stats.channel}_{current_datetime}.png'
                    
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmpfile:
                        plt.savefig(tmpfile.name)

                        nuevo_archivo = PlotData()
                        nuevo_archivo.image_path.save(image_filename, tmpfile)
                        nuevo_archivo.save()

                        serializer = PlotDataSerializer(nuevo_archivo)
                    
                    os.unlink(tmpfile.name)

                    file_url = request.build_absolute_uri(serializer.data['image_path'])
           
            return Response({ "url" : file_url}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'POST'])
def trace_data(request):
    
    if request.method == 'GET':       
       dd = ''
    elif request.method == 'POST':
        data_str = request.data.get('data')
        station_data = request.data.get('station_selected')
        channel_data = request.data.get('channel_selected')
        unit = request.data.get('unit', '')

        if not data_str:
            raise APIException('No se proporcionó datos para Lectura')
        try:
            sts = obspy.read(data_str)
            sts.merge(method=1, fill_value= 'latest')
            inventory = read_inventory_safe(data_str)

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
                try:
                    if station.stats.kinemetrics_evt.chan_id == channel_data:
                        channel_data = station.stats.channel
                except:
                    channel_data = channel_data

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
                    elif unit == 'mg':
                        st1_data = st1.data * station.stats.calib 
                        st3_data = st3.data * station.stats.calib 
                        st5_data = st5.data * station.stats.calib 
                        unit_a, unit_v, unit_d = 'mg', 'cm/s', 'cm'
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

                    sendData = {
                        "formato" : format_file,

                        "trace_a_unit"  :  unit_a,
                        "traces_a" : st1_data.tolist(),
                        "peak_a"   : pga_a_value,

                        "trace_v_unit" : unit_v,
                        "traces_v" : st3_data.tolist(),
                        "peak_v"   : pga_v_value,

                        "trace_d_unit" : unit_d,
                        "traces_d" : st5_data.tolist(),
                        "peak_d"   : pga_d_value,

                        "tiempo_a" : tiempo.tolist()
                    }         
            
            return Response( [sendData] , status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'POST'])
def data_process(request):
    
    if request.method == 'GET':       
       dd = ''
    elif request.method == 'POST':
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
            raise APIException('No se proporcionó datos para Lectura')
        try:
            sts = obspy.read(data_str)
            sts.merge(method=1, fill_value= 'latest')
            inventory = read_inventory_safe(data_str)

            if t_min and t_max:
                min_time = obspy.UTCDateTime(t_min)
                max_time = obspy.UTCDateTime(t_max)
                sts.trim(min_time,max_time)

            if baseline_type:
                sts.detrend(type=baseline_type)

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
                try:
                    if station.stats.kinemetrics_evt.chan_id == channel_data:
                        channel_data = station.stats.channel
                except:
                    channel_data = channel_data

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
                            if convert_to_unit == 'mg':
                                st1_data = st1.data * station.stats.calib * 1.020
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'mg', 'cm/s', 'cm'
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
                                st1_data = st1.data * station.stats.calib * 0.102
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                            if convert_to_unit == 'mg':
                                st1_data = st1.data * station.stats.calib * 102.04
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'mG', 'm/s', 'm'
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
                                cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                            if convert_to_unit == 'mg':
                                st1_data = st1.data * station.stats.calib * 1000
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'mg', 'm/s', 'm'
                        if convert_from_unit == 'mg':
                            if convert_to_unit == 'm':
                                st1_data = st1.data * station.stats.calib * 0.0098
                                st3_data = st3.data * station.stats.calib * 0.0098
                                st5_data = st5.data * station.stats.calib * 0.0098
                                cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                            if convert_to_unit == 'gal' :
                                st1_data = st1.data * station.stats.calib * 0.980
                                st3_data = st3.data * station.stats.calib * 0.980
                                st5_data = st5.data * station.stats.calib * 0.980
                                cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                            if convert_to_unit == 'g':
                                st1_data = st1.data * station.stats.calib * 0.001
                                st3_data = st3.data * station.stats.calib * 0.981
                                st5_data = st5.data * station.stats.calib * 0.981
                                cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                            if convert_to_unit == 'mg' or convert_to_unit == '':
                                st1_data = st1.data * station.stats.calib * 1
                                st3_data = st3.data * station.stats.calib * 0.980
                                st5_data = st5.data * station.stats.calib * 0.980
                                cuv1, cuv2, cuv3 = 'mg', 'cm/s', 'cm'
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

                    sendData = {
                        "formato" : format_file,
                        
                        "trace_a_unit" : cuv1,
                        "traces_a" : st1_data.tolist(),
                        "peak_a" : pga_a_value,

                        "trace_v_unit" : cuv2,
                        "traces_v" : st3_data.tolist(),
                        "peak_v" : pga_v_value,

                        "trace_d_unit" : cuv3,
                        "traces_d" : st5_data.tolist(),
                        "peak_d" : pga_d_value,

                        "tiempo_a" : tiempo.tolist()
                    }
         
            if not sendData:
                return Response({'error': 'No se encontraron datos para enviar'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response([sendData], status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'POST'])
def data_plot_process(request):
    
    if request.method == 'GET':       
       dd = ''
    elif request.method == 'POST':
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

        graph_color = request.data.get('graph_color', 'b')

        if not data_str:
            raise APIException('No se proporcionó datos para Lectura')
        try:
            sts = obspy.read(data_str)
            sts.merge(method=1, fill_value= 'latest')
            inventory = read_inventory_safe(data_str)

            if t_min and t_max:
                min_time = obspy.UTCDateTime(t_min)
                max_time = obspy.UTCDateTime(t_max)
                sts.trim(min_time,max_time)

            if baseline_type:
                sts.detrend(type=baseline_type)

            unit_found = ''
            saved_instances = []
            station_full_name = ''

            if inventory:
                for net in inventory:
                    for sta in net:
                        if(sta.code == station_data):
                            for cha in sta:
                                unit_found = cha.response.instrument_sensitivity.input_units    

                sts.attach_response(inventory)            
                sts.remove_sensitivity()

            for station in sts:
                try:
                    if station.stats.kinemetrics_evt.chan_id == channel_data:
                        channel_data = station.stats.channel
                        station_full_name = f'{station.stats.network}.{station.stats.station}.{station.stats.location}.{station.stats.kinemetrics_evt.chan_id}'
                except:
                    channel_data = channel_data
                    station_full_name = f'{station.stats.network}.{station.stats.station}.{station.stats.location}.{station.stats.channel}'

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
                            if convert_to_unit == 'mg':
                                st1_data = st1.data * station.stats.calib * 1.020
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'mg', 'cm/s', 'cm'
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
                                st1_data = st1.data * station.stats.calib * 0.102
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                            if convert_to_unit == 'mg':
                                st1_data = st1.data * station.stats.calib * 102.04
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'mG', 'm/s', 'm'
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
                                cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                            if convert_to_unit == 'mg':
                                st1_data = st1.data * station.stats.calib * 1000
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'mg', 'm/s', 'm'
                        if convert_from_unit == 'mg':
                            if convert_to_unit == 'm':
                                st1_data = st1.data * station.stats.calib * 0.0098
                                st3_data = st3.data * station.stats.calib * 0.0098
                                st5_data = st5.data * station.stats.calib * 0.0098
                                cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                            if convert_to_unit == 'gal' :
                                st1_data = st1.data * station.stats.calib * 0.980
                                st3_data = st3.data * station.stats.calib * 0.980
                                st5_data = st5.data * station.stats.calib * 0.980
                                cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                            if convert_to_unit == 'g':
                                st1_data = st1.data * station.stats.calib * 0.001
                                st3_data = st3.data * station.stats.calib * 0.981
                                st5_data = st5.data * station.stats.calib * 0.981
                                cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                            if convert_to_unit == 'mg' or convert_to_unit == '':
                                st1_data = st1.data * station.stats.calib * 1
                                st3_data = st3.data * station.stats.calib * 0.980
                                st5_data = st5.data * station.stats.calib * 0.980
                                cuv1, cuv2, cuv3 = 'mg', 'cm/s', 'cm'
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
                    pga_a_value = format_value(max_abs_a_value)

                    max_abs_v_value = max(np.max(st3_data), np.min(st3_data), key=abs)
                    pga_v_value = format_value(max_abs_v_value)

                    max_abs_d_value = max(np.max(st5_data), np.min(st5_data), key=abs)
                    pga_d_value = format_value(max_abs_d_value)

                    utc = 0

                    fig = plt.figure(figsize=(10,8))

                    try: 
                        marca_de_agua = mpimg.imread('/var/www/apiqs.ncn.pe/ncnsis/static/ncnLogoColor.png')
                    except:
                        marca_de_agua = mpimg.imread('static/ncnLogoColor.png')
                    fig.figimage(marca_de_agua, 300, 200, alpha=0.09)

                    ax = fig.add_subplot(311)

                    # ttac2 = str(UTCDateTime(station.stats.starttime) + utc*3600).split("T")
                    ttac2 = str(UTCDateTime(station.stats.starttime)).split("T")
                    titulo_hora  = "Fecha: " + ttac2[0] + " / Hora: " + ttac2[1][0:8] + " UTC " + str(utc)

                    ax.set_title(station.stats.network +'.' + station.stats.station + '.'+ station.stats.location +' / ' + str(titulo_hora) )

                    sy = st1_data
                    st = station_full_name
                    ax.text(0.01, 0.95, st ,verticalalignment='top', horizontalalignment='left',transform=ax.transAxes,color='k', fontsize=10)
                    ax.text(0.81, 0.95,'PGA: '+str(pga_a_value)+f' {cuv1}',horizontalalignment='left',verticalalignment='top',transform = ax.transAxes)
                    plt.plot(tiempo, sy,graph_color,linewidth=0.3)
                    plt.ylabel(f'Aceleracion [{cuv1}]')
                    plt.grid()

                    ax1 = fig.add_subplot(312, sharex=ax)
                    sy1 = st3_data
                    st1 = station_full_name
                    ax1.text(0.01, 0.95,st1,verticalalignment='top', horizontalalignment='left',transform=ax1.transAxes,color='k', fontsize=10)
                    ax1.text(0.81, 0.95,'PGV: '+str(pga_v_value)+ f' {cuv2}',horizontalalignment='left',verticalalignment='top',transform = ax1.transAxes)
                    plt.plot(tiempo, sy1,graph_color,linewidth=0.3)
                    plt.ylabel(f'Velocidad [{cuv2}]')
                    plt.grid()

                    ax2 = fig.add_subplot(313, sharex=ax)
                    sy2 = st5_data
                    st2 = station_full_name
                    ax2.text(0.01, 0.95,st2,verticalalignment='top', horizontalalignment='left',transform=ax2.transAxes,color='k', fontsize=10)
                    ax2.text(0.81, 0.95,'PGD: '+str(pga_d_value)+f' {cuv3}',horizontalalignment='left',verticalalignment='top',transform = ax2.transAxes)
                    plt.plot(tiempo, sy2,graph_color,linewidth=0.3)
                    plt.ylabel(f'Desplazamiento [{cuv3}]')
                    plt.grid()
                  
                    current_datetime = datetime.now().strftime('%Y%m%d_%H%M%S')

                    image_filename = f'{station.stats.station}_{station.stats.channel}_{current_datetime}.png'
                    
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmpfile:
                        plt.savefig(tmpfile.name)

                        nuevo_archivo = PlotData()
                        nuevo_archivo.image_path.save(image_filename, tmpfile)
                        nuevo_archivo.save()

                        serializer = PlotDataSerializer(nuevo_archivo)
                    
                    os.unlink(tmpfile.name)

                    file_url = request.build_absolute_uri(serializer.data['image_path'])
         
            return Response({ "url" : file_url}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'POST'])
def data_plot_auto(request):
    
    if request.method == 'GET':       
       dd = ''
    elif request.method == 'POST':
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

        graph_color = request.data.get('graph_color', 'b')

        if not data_str:
            raise APIException('No se proporcionó datos para Lectura')
        try:
            baseline_type = 'linear'
            filter_type = 'bandpass'
            freq_min = 0.1
            freq_max = 25
            corner = 2
            zero_ph = True
            convert_to_unit = 'gal'

            sts = obspy.read(data_str)

            sts.merge(method=1, fill_value= 'latest')
            inventory = read_inventory_safe(data_str)

            if t_min and t_max:
                min_time = obspy.UTCDateTime(t_min)
                max_time = obspy.UTCDateTime(t_max)
                sts.trim(min_time,max_time)

            if baseline_type:
                sts.detrend(type=baseline_type)

            unit_found = ''
            saved_instances = []
            station_full_name = ''

            if inventory:
                for net in inventory:
                    for sta in net:
                        if(sta.code == station_data):
                            for cha in sta:
                                unit_found = cha.response.instrument_sensitivity.input_units    

                sts.attach_response(inventory)            
                sts.remove_sensitivity()

            for station in sts:
                try:
                    if station.stats.kinemetrics_evt.chan_id == channel_data:
                        channel_data = station.stats.channel
                        station_full_name = f'{station.stats.network}.{station.stats.station}.{station.stats.location}.{station.stats.kinemetrics_evt.chan_id}'
                except:
                    channel_data = channel_data
                    station_full_name = f'{station.stats.network}.{station.stats.station}.{station.stats.location}.{station.stats.channel}'

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
                            if convert_to_unit == 'mg':
                                st1_data = st1.data * station.stats.calib * 1.020
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'mg', 'cm/s', 'cm'
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
                                st1_data = st1.data * station.stats.calib * 0.102
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                            if convert_to_unit == 'mg':
                                st1_data = st1.data * station.stats.calib * 102.04
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'mG', 'm/s', 'm'
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
                                cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                            if convert_to_unit == 'mg':
                                st1_data = st1.data * station.stats.calib * 1000
                                st3_data = st3.data * station.stats.calib * 1
                                st5_data = st5.data * station.stats.calib * 1
                                cuv1, cuv2, cuv3 = 'mg', 'm/s', 'm'
                        if convert_from_unit == 'mg':
                            if convert_to_unit == 'm':
                                st1_data = st1.data * station.stats.calib * 0.0098
                                st3_data = st3.data * station.stats.calib * 0.0098
                                st5_data = st5.data * station.stats.calib * 0.0098
                                cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                            if convert_to_unit == 'gal' :
                                st1_data = st1.data * station.stats.calib * 0.980
                                st3_data = st3.data * station.stats.calib * 0.980
                                st5_data = st5.data * station.stats.calib * 0.980
                                cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                            if convert_to_unit == 'g':
                                st1_data = st1.data * station.stats.calib * 0.001
                                st3_data = st3.data * station.stats.calib * 0.981
                                st5_data = st5.data * station.stats.calib * 0.981
                                cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                            if convert_to_unit == 'mg' or convert_to_unit == '':
                                st1_data = st1.data * station.stats.calib * 1
                                st3_data = st3.data * station.stats.calib * 0.980
                                st5_data = st5.data * station.stats.calib * 0.980
                                cuv1, cuv2, cuv3 = 'mg', 'cm/s', 'cm'
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
                    pga_a_value = format_value(max_abs_a_value)

                    max_abs_v_value = max(np.max(st3_data), np.min(st3_data), key=abs)
                    pga_v_value = format_value(max_abs_v_value)

                    max_abs_d_value = max(np.max(st5_data), np.min(st5_data), key=abs)
                    pga_d_value = format_value(max_abs_d_value)

                    utc = 0

                    fig = plt.figure(figsize=(10,8))
                    
                    try: 
                        marca_de_agua = mpimg.imread('/var/www/apiqs.ncn.pe/ncnsis/static/ncnLogoColor.png')
                    except:
                        marca_de_agua = mpimg.imread('static/ncnLogoColor.png')
                    fig.figimage(marca_de_agua, 300, 200, alpha=0.09)

                    ax = fig.add_subplot(311)

                    ttac2 = str(UTCDateTime(station.stats.starttime)).split("T")
                    titulo_hora  = "Fecha: " + ttac2[0] + " / Hora: " + ttac2[1][0:8] + " UTC " + str(utc)

                    ax.set_title(station.stats.network +'.' + station.stats.station + '.'+ station.stats.location +' / ' + str(titulo_hora) )

                    sy = st1_data
                    st = station_full_name
                    ax.text(0.01, 0.95, st ,verticalalignment='top', horizontalalignment='left',transform=ax.transAxes,color='k', fontsize=10)
                    ax.text(0.81, 0.95,'PGA: '+str(pga_a_value)+f' {cuv1}',horizontalalignment='left',verticalalignment='top',transform = ax.transAxes)
                    plt.plot(tiempo, sy,graph_color,linewidth=0.3)
                    plt.ylabel(f'Aceleracion [{cuv1}]')
                    plt.grid()

                    ax1 = fig.add_subplot(312, sharex=ax)
                    sy1 = st3_data
                    st1 = station_full_name
                    ax1.text(0.01, 0.95,st1,verticalalignment='top', horizontalalignment='left',transform=ax1.transAxes,color='k', fontsize=10)
                    ax1.text(0.81, 0.95,'PGV: '+str(pga_v_value)+ f' {cuv2}',horizontalalignment='left',verticalalignment='top',transform = ax1.transAxes)
                    plt.plot(tiempo, sy1,graph_color,linewidth=0.3)
                    plt.ylabel(f'Velocidad [{cuv2}]')
                    plt.grid()

                    ax2 = fig.add_subplot(313, sharex=ax)
                    sy2 = st5_data
                    st2 = station_full_name
                    ax2.text(0.01, 0.95,st2,verticalalignment='top', horizontalalignment='left',transform=ax2.transAxes,color='k', fontsize=10)
                    ax2.text(0.81, 0.95,'PGD: '+str(pga_d_value)+f' {cuv3}',horizontalalignment='left',verticalalignment='top',transform = ax2.transAxes)
                    plt.plot(tiempo, sy2,graph_color,linewidth=0.3)
                    plt.ylabel(f'Desplazamiento [{cuv3}]')
                    plt.grid()
                  
                    current_datetime = datetime.now().strftime('%Y%m%d_%H%M%S')

                    image_filename = f'{station.stats.station}_{station.stats.channel}_{current_datetime}.png'
                    
                    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmpfile:
                        plt.savefig(tmpfile.name)

                        nuevo_archivo = PlotData()
                        nuevo_archivo.image_path.save(image_filename, tmpfile)
                        nuevo_archivo.save()

                        serializer = PlotDataSerializer(nuevo_archivo)
                    
                    os.unlink(tmpfile.name)

                    file_url = request.build_absolute_uri(serializer.data['image_path'])
         
            return Response({ "url" : file_url}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)


# ----------------------------------------------------------------------


@api_view(['GET', 'POST'])
def convert_stream(request):
    
    if request.method == 'GET':       
       dd = ''
    elif request.method == 'POST':
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
                stTime = f['starttime']

                if stTime != '':
                    st_time = obspy.UTCDateTime(stTime)
                else:
                    st_time = obspy.UTCDateTime(datetime.datetime.now())

                for key, value in f.items():
                    if key.startswith('c_'):
                        channel_number = key[2:]  
                        if channel_number not in trace_data_dict:
                            trace_data_dict[channel_number] = {'data': [], 'channel': ''}

                        if value != 'T':  
                            trace_data_dict[channel_number]['data'].extend(value) 

                    elif key.startswith('cc_'):
                        channel_number = key[3:]  
                        if channel_number in trace_data_dict:
                            trace_data_dict[channel_number]['channel'] = value  

                        
                        if value == 'T' and not delta_calculated:
                            data_time = f['c_' + channel_number]  
                            delta = data_time[1] - data_time[0] 
                            delta_calculated = True
                    
                    elif key.startswith('ccc_'):
                        channel_number = key[4:] 
                        if channel_number in trace_data_dict:
                           value_multiplier = value
                           trace_data_dict[channel_number]['data'] = [x * value_multiplier for x in trace_data_dict[channel_number]['data']]

            for channel_number, data_info in trace_data_dict.items():
               
                if data_info['channel'].upper() != 'T':
                    array_np = np.array(data_info['data'], dtype=np.float64)
                    array_np = array_np.flatten()

                    trace = Trace(data=array_np, header={
                        'network': net,
                        'station': sta,
                        'location': loca,
                        'delta': delta,
                        'starttime': st_time
                    })
                    trace.stats.channel = data_info['channel']
                    stream.append(trace)
           
            unique_filename =  f"GEN_{uuid.uuid4().hex}.mseed"
 
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

@api_view(['GET', 'POST'])
def auto_adjust(request):
    
    if request.method == 'GET':       
       dd = ''
    elif request.method == 'POST':
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
            raise APIException('No se proporcionó datos para Lectura')
        try:
            baseline_type = 'linear'
            filter_type = 'bandpass'
            freq_min = 0.1
            freq_max = 25
            corner = 2
            zero_ph = True
            convert_to_unit = 'gal'

            sts = obspy.read(data_str)
            sts.merge(method=1, fill_value= 'latest')
            inventory = read_inventory_safe(data_str)

            sts.detrend(type=baseline_type)

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
                try:
                    if station.stats.kinemetrics_evt.chan_id == channel_data:
                        channel_data = station.stats.channel
                except:
                    channel_data = channel_data
                    
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
                        if convert_from_unit == 'mg':
                            if convert_to_unit == 'm':
                                st1_data = st1.data * station.stats.calib * 0.0098
                                st3_data = st3.data * station.stats.calib * 0.0098
                                st5_data = st5.data * station.stats.calib * 0.0098
                                cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                            if convert_to_unit == 'gal' :
                                st1_data = st1.data * station.stats.calib * 0.981
                                st3_data = st3.data * station.stats.calib * 0.981
                                st5_data = st5.data * station.stats.calib * 0.981
                                cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                            if convert_to_unit == 'g':
                                st1_data = st1.data * station.stats.calib * 0.001
                                st3_data = st3.data * station.stats.calib * 0.981
                                st5_data = st5.data * station.stats.calib * 0.981
                                cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                            if convert_to_unit == 'mg' or convert_to_unit == '':
                                st1_data = st1.data * station.stats.calib * 1
                                st3_data = st3.data * station.stats.calib * 0.981
                                st5_data = st5.data * station.stats.calib * 0.981
                                cuv1, cuv2, cuv3 = 'mg', 'cm/s', 'cm'
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

                    sendData = {
                        "formato" : format_file,
                        
                        "trace_a_unit" : cuv1,
                        "traces_a" : st1_data.tolist(),
                        "peak_a" : pga_a_value,

                        "trace_v_unit" : cuv2,
                        "traces_v" : st3_data.tolist(),
                        "peak_v" : pga_v_value,

                        "trace_d_unit" : cuv3,
                        "traces_d" : st5_data.tolist(),
                        "peak_d" : pga_d_value,

                        "tiempo_a" : tiempo.tolist()
                    }
         
            if not sendData:
                return Response({'error': 'No se encontraron datos para enviar'}, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response([sendData], status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
def files_uploaded(request):
    if request.method == 'GET': 
        elementos = UploadFile.objects.all()
        serializer = FileUploadSerializer(elementos, many=True)
        sendData = []
        
        for s in serializer.data:
            if(s['file']):
                sendData.append({
                    "id" : s['id'],
                    "file" : request.build_absolute_uri(s['file']),
                    "string_data" : '',
                    "ip": s['ip'],
                    "fecha_creacion": s['fecha_creacion'],
                })
            else:
                sendData.append({
                    "id" : s['id'],
                    "file" : '',
                    "string_data" : request.build_absolute_uri(s['string_data']),
                    "ip": s['ip'],
                    "fecha_creacion": s['fecha_creacion'],
                })
        return Response(sendData, status=status.HTTP_201_CREATED)


# ------------------------------------------------------------------------

@api_view(['POST'])
def crear_usuario(request):
    if 'username' in request.data and 'email' in request.data and 'g' in request.data:
        username = request.data['username']
        email = request.data['email']
        group = request.data['g']

        if not validators.email(email):
            return Response({'error': 'Formato de correo electrónico no válido'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists() or User.objects.filter(username=username).exists():
            user_instance = User.objects.filter(email=email).first() or User.objects.filter(username=username).first()
            return Response(user_instance.pk, status=status.HTTP_200_OK)
        else:
            nuevo_usuario = User.objects.create_user(
                username=username,
                email=email
            )
            nuevo_usuario.save()
            
            if group == 10:
                nuevo_payuser = PayUser.objects.create(
                    user=nuevo_usuario,
                    payed=True  
                )
            else:
                nuevo_payuser = PayUser.objects.create(
                    user=nuevo_usuario,
                    payed=False  
                )

            nuevo_payuser.save()
            return Response(nuevo_usuario.pk,status=status.HTTP_201_CREATED)
    else:
        return Response({"msg": "error"}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'POST'])
def upload_file_user(request):
    
    if request.method == 'GET':       
       dd = ''
    elif request.method == 'POST':
        try:
            uploaded_file = request.FILES.get('file')
            string_data = request.data.get('string_data', '')
            id_user = request.data.get('user', '')

            user_instance = User.objects.get(pk=id_user)

            if uploaded_file:
                file = UploadFileUser(user=user_instance, file=uploaded_file)
                file.save()
                serializer = FileUploadUserSerializer(file)
                file_url = request.build_absolute_uri(serializer.data['file'])

                filename = file_url.split('/')[-1]
                extension = splitext(filename)[1]

                try:
                    if extension == '.txt':
                        format_file = 'TXT'
                    else :
                        st = obspy.read(file_url)
                        format_file = st[0].stats._format
                except:
                    format_file = ''
                    # os.remove(os.path.join(settings.MEDIA_ROOT, serializer.data['file'] ))
                    # file.delete()
                    return Response({'error': 'Formato no valido'}, status=status.HTTP_406_NOT_ACCEPTABLE)
                return Response({
                    'file': file_url,
                    'string_data': None,
                    'f' : format_file
                }, status=status.HTTP_201_CREATED)

            elif string_data:
                if validators.url(string_data):
                    url = UploadFileUser(user=user_instance, string_data=string_data)
                    url.save()
                    serializer = FileUploadUserSerializer(url)
                    string_url = request.build_absolute_uri(serializer.data['string_data'])

                    filename  = string_url.split('/')[-1]
                    extension = splitext(filename)[1]

                    try:
                        if extension == '.txt':
                            format_file = 'TXT'
                        else :
                            st = obspy.read(string_url)
                            format_file = st[0].stats._format
                    except:
                        format_file = ''
                        # os.remove(os.path.join(settings.MEDIA_ROOT, serializer.data['file'] ))
                        # url.delete()
                        return Response({'error': 'Formato no valido'}, status=status.HTTP_406_NOT_ACCEPTABLE)
                    return Response({
                        'file': None,
                        'string_data': string_url,
                        'f' : format_file
                    }, status=status.HTTP_201_CREATED)
                else:
                    raise ValidationError('La cadena de datos no es una URL válida.')
            
            else:
                raise ValidationError('No se proporcionaron datos.')

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        
@api_view(['GET', 'POST'])
def mseed_xml_user(request):

    if request.method == 'GET':       
       dd = ''
       return Response({'data': 'D'}, status=status.HTTP_201_CREATED)
    
    elif request.method == 'POST':
       
        mseed_file = request.data.get('mseed_file', '')
        xml_file   = request.data.get('xml_file', '')
        calib_fac = request.data.get('calib_factor', '')
        id_user = request.data.get('user', '')

        try:
            user_instance = User.objects.get(pk=id_user)
            
            if calib_fac and mseed_file:
                sta_mseed = obspy.read(mseed_file)
                sta_mseed.merge(method=1)
                stream = Stream()

                calib_factor = []

                for i, trace in enumerate(sta_mseed):
                    factor_key = f'c_{i}'  
                    factor = calib_fac.get(factor_key, 1)  
                    
                    trace.data = trace.data.astype(np.float64)  
                    trace.data *= factor

                    calib_entry = CalibTraces.objects.filter(
                        user=user_instance,
                        network=trace.stats.network,
                        station=trace.stats.station,
                        location=trace.stats.location,
                        channel=trace.stats.channel,
                        units=calib_fac.get('unitst')
                    ).first()

                    if calib_entry:
                        calib_entry.calib = factor
                        calib_entry.save()

                    else:
                        nuevo_calib = CalibTraces(
                            user=user_instance, 
                            network=trace.stats.network,
                            station=trace.stats.station,
                            location=trace.stats.location,
                            channel=trace.stats.channel,
                            calib=factor,
                            units=calib_fac.get('unitst')
                        )

                        nuevo_calib.save()

                unique_filename =  f"GEN_{uuid.uuid4().hex}.mseed"
    
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    sta_mseed.write(temp_file.name, format="MSEED")

                    nuevo_archivo = UploadFileUser(user=user_instance)
                    nuevo_archivo.file.save(unique_filename, temp_file)
                    nuevo_archivo.save()

                    serializer = FileUploadUserSerializer(nuevo_archivo)


                os.unlink(temp_file.name)

                file_url = request.build_absolute_uri(serializer.data['file'])

                return Response({'url':file_url}, status=status.HTTP_201_CREATED)
            
            elif mseed_file and xml_file:

                sta_mseed = obspy.read(mseed_file)
                
                sta_xml = obspy.read_inventory(xml_file)

                sens_found = []

                stations_inventory = {f"{net.code}.{sta.code}.{cha.location_code}.{cha.code}" 
                                    for net in sta_xml for sta in net for cha in sta}
            
                stations_mseed = {f"{strs.stats.network}.{strs.stats.station}.{strs.stats.location}.{strs.stats.channel}" 
                                for strs in sta_mseed}

                common_stations = stations_inventory.intersection(stations_mseed)

                for station in common_stations:
                    for net in sta_xml:
                        for sta in net:
                            for cha in sta:
                                if f"{net.code}.{sta.code}.{cha.location_code}.{cha.code}" == station:
                                    sens_found.append({
                                        "station": f'{net.code}.{sta.code}.{cha.location_code}.{cha.code}',
                                        "calib": 1 / cha.response.instrument_sensitivity.value,
                                        "unit": cha.response.instrument_sensitivity.input_units
                                    })
                                    break  
                            else:
                                continue
                            break
                unit = ''

                while len(sens_found) > 0:
                    if sens_found[0]['unit'] == 'M/S**2':
                        unit = 'm'
                        break
                    elif sens_found[0]['unit'] == 'CM/S**2':
                        unit= 'cm'
                        break
                    elif sens_found[0]['unit'] == 'G':
                        unit= 'g'
                        break
                    else:
                        unit = ''
                        break
                
                if len(sens_found) == 0:
                    return Response({"error" : 'No se encontraron similitudes con las Estaciones'}, status=status.HTTP_406_NOT_ACCEPTABLE)

                try:
                    sta_invSta = sta_xml.select(station=sta_mseed[0].stats.station)
                    sta_mseed.attach_response(sta_invSta)
                    sta_mseed.remove_sensitivity()
                except:
                    d = ''

                unique_filename =  f"GEN_{uuid.uuid4().hex}.mseed"
    
                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                    sta_mseed.write(temp_file.name, format="MSEED")

                    nuevo_archivo = UploadFileUser(user=user_instance)
                    nuevo_archivo.file.save(unique_filename, temp_file)
                    nuevo_archivo.save()

                    serializer = FileUploadUserSerializer(nuevo_archivo)

                os.unlink(temp_file.name)

                file_url = request.build_absolute_uri(serializer.data['file'])

                return Response({'url':file_url, 'unit': unit}, status=status.HTTP_201_CREATED)
            
            else:
                return Response({"error" : 'No se proporcio los datos'}, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET', 'POST'])
def mseed_calib_fact(request):
    if request.method == 'POST':

        id_user    = request.data.get('user', '')
        m_network  = request.data.get('network', '')
        m_station  = request.data.get('station', '')
        m_location = request.data.get('location', '')
        m_channel  = request.data.get('channel', '')

        try:
            # user_instance = User.objects.get(pk=id_user)

            calib_entry = CalibTraces.objects.filter(
                        user_id  = id_user,
                        # network  = m_network,
                        # station  = m_station,
                        # location = m_location,
            )

            serializer = CalibTracesSerializer(calib_entry, many=True)

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

@api_view(['DELETE', 'POST', 'PUT'])     
def crear_proyecto(request):   
    if request.method == 'POST':
        username = request.data['username']
        email = request.data['email']

        if User.objects.filter(email=email).exists() or User.objects.filter(username=username).exists():
            
            user_instance = User.objects.filter(email=email).first() or User.objects.filter(username=username).first()
            
            count_proj    = Proyecto.objects.filter(user=user_instance).count()

            pay_user      = PayUser.objects.get(user=user_instance)

            if count_proj >= 5 and pay_user.payed == False:
                return Response({"msg" : 'Limite de Proyectos Permitidos' }, status=status.HTTP_200_OK)
            else:
                new_project   = Proyecto.objects.create(user=user_instance)
                new_project.save()

            return Response({"id" : new_project.uuid }, status=status.HTTP_200_OK) 
        else:
            return Response({"msg": "error"}, status=status.HTTP_400_BAD_REQUEST)
    
    if request.method == 'DELETE':
        project_uuid = request.GET.get('id')

        if Proyecto.objects.filter(uuid=project_uuid).exists():
            proyecto_ext = Proyecto.objects.get(uuid=project_uuid)
            proyecto_ext.delete()
            return Response({"msg" : "proyecto Existe y fue borrado" }, status=status.HTTP_200_OK)
        else:
            return Response({"msg": "error"}, status=status.HTTP_404_NOT_FOUND)
        
    if request.method == 'PUT':
        project_uuid = request.GET.get('id')

        nombre_proj  = request.data.get('name', '')
        descrp_proj  = request.data.get('desp', '')

        uploaded_img = None

        if 'img_proj' in request.FILES:
            uploaded_img = request.FILES['img_proj']
                

        if Proyecto.objects.filter(uuid=project_uuid).exists():
            proyecto_ext = Proyecto.objects.get(uuid=project_uuid)
            proyecto_ext.name = nombre_proj
            proyecto_ext.desp = descrp_proj
            
            if uploaded_img:
                proyecto_ext.img = uploaded_img
            else:
                proyecto_ext.img = proyecto_ext.img 

            proyecto_ext.save()
            
            return Response({"msg" : "proyecto actualizado" }, status=status.HTTP_200_OK)
        else:
            return Response({"msg": "error"}, status=status.HTTP_404_NOT_FOUND)
    else:
        return Response({'msg': 'Method not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)
        
@api_view(['PUT'])     
def update_project_tab(request): 
    if request.method == 'PUT':
        project_uuid = request.GET.get('id')
        save_tab = request.data.get('tab', '')

        if Proyecto.objects.filter(uuid=project_uuid).exists():
            proyecto_ext = Proyecto.objects.get(uuid=project_uuid)
            proyecto_ext.tab = save_tab
            proyecto_ext.save()
            
            return Response({"msg" : "proyecto Existe y fue borrado" }, status=status.HTTP_200_OK)
        else:
            return Response({"msg": "error"}, status=status.HTTP_404_NOT_FOUND)
    else:
        return Response({'error': 'Method not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

@api_view(['DELETE', 'POST', 'PUT'])     
def file_project(request): 
    if request.method == 'POST':
        try:
            uploaded_file = request.FILES.get('file')
            string_data = request.data.get('string_data', '')
            id_user = request.data.get('user', '')
            id_proyecto = request.data.get('pro', '')
            filename = request.data.get('filename', '')
            status_file = request.data.get('status', '')
            
            user_instance = User.objects.get(pk=id_user)
            projecto_instance = Proyecto.objects.get(uuid=id_proyecto)
            
            nro_archivos = ProyectoFiles.objects.filter(proyecto=projecto_instance).count()

            pay_user      = PayUser.objects.get(user=user_instance)

            if nro_archivos >= 5 and pay_user.payed == False:
                return Response({"msg" : "Limite de Archivos Permitidos" }, status=status.HTTP_200_OK)
            else:
                if uploaded_file:

                    file = ProyectoFiles(proyecto=projecto_instance, user=user_instance, file=uploaded_file, filename=filename, status=status_file)
                    file.save()

                    serializer = ProyectoFilesSerializer(file)
                    file_url = request.build_absolute_uri(serializer.data['file'])

                    filename = file_url.split('/')[-1]
                    extension = splitext(filename)[1]

                    try:
                        if extension == '.txt':
                            format_file = 'TXT'
                        else :
                            st = obspy.read(file_url)
                            format_file = st[0].stats._format
                    except:
                        format_file = ''
                        # os.remove(os.path.join(settings.MEDIA_ROOT, serializer.data['file'] ))
                        # file.delete()
                        return Response({'error': 'Formato no valido'}, status=status.HTTP_406_NOT_ACCEPTABLE)
                    
                    return Response({
                        'id': serializer.data['id'],
                        'file': file_url,
                        'string_data': None,
                        'f' : format_file
                    }, status=status.HTTP_201_CREATED)

                elif string_data:
                    if validators.url(string_data):
                        url = ProyectoFiles(proyecto=projecto_instance, user=user_instance, string_data=string_data)
                        url.save()

                        serializer = ProyectoFilesSerializer(url)
                        string_url = request.build_absolute_uri(serializer.data['string_data'])

                        filename  = string_url.split('/')[-1]
                        extension = splitext(filename)[1]

                        try:
                            if extension == '.txt':
                                format_file = 'TXT'
                            else :
                                st = obspy.read(string_url)
                                format_file = st[0].stats._format
                        except Exception as e:
                            format_file = ''
                            # os.remove(os.path.join(settings.MEDIA_ROOT, serializer.data['file'] ))
                            # url.delete()
                            return Response({'error': 'Datos Invalidos'}, status=status.HTTP_406_NOT_ACCEPTABLE)
                        return Response({
                            'id': serializer.data['id'],
                            'file': None,
                            'string_data': string_url,
                            'f' : format_file
                        }, status=status.HTTP_201_CREATED)
                    else:
                        raise ValidationError('La cadena de datos no es una URL válida.')
                else:
                    raise ValidationError('No se proporcionaron datos.')
        except Exception as e:
            return Response({"error" : 'No se proporcio los datos'}, status=status.HTTP_400_BAD_REQUEST)
    if request.method == 'DELETE':
        file_id = request.GET.get('id')

        if ProyectoFiles.objects.filter(id=file_id).exists():
            pro_f_ext = ProyectoFiles.objects.get(id=file_id)
            pro_f_ext.delete()
            return Response({"msg" : "Borrado" }, status=status.HTTP_200_OK)
        else:
            return Response({"msg": "error"}, status=status.HTTP_404_NOT_FOUND)
    if request.method == 'PUT':
        file_id = request.GET.get('id')

        file_url    = request.data.get('url_gen', '')
        unit_file   = request.data.get('unit', '')
        status_file = request.data.get('status', '')
        extra_file  = request.data.get('extra', '')


        if ProyectoFiles.objects.filter(id=file_id).exists():

            pro_f_ext = ProyectoFiles.objects.get(id=file_id)

            pro_f_ext.url_gen = file_url
            pro_f_ext.unit    = unit_file
            pro_f_ext.status  = status_file
            pro_f_ext.extra   = extra_file
            pro_f_ext.save()
            return Response({"msg" : "Update" }, status=status.HTTP_200_OK)
        else:
            return Response({"msg": "error"}, status=status.HTTP_404_NOT_FOUND)
        
    else:
        return Response({'error': 'Method not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

@api_view(['GET','POST'])
def user_proyecto(request):

    if request.method == 'POST':
        username = request.data.get('username', '')
        email = request.data.get('email', '')

        if User.objects.filter(email=email).exists() or User.objects.filter(username=username).exists():
            user_instance = User.objects.filter(email=email).first() or User.objects.filter(username=username).first()
            
            list_project = Proyecto.objects.filter(user=user_instance)

            serializer_proj = ProyectoSerializer(list_project, many=True)

            proyectos_list = [] 
        
            for proyecto, ser_pro in zip(list_project, serializer_proj.data):
                archivos = ProyectoFiles.objects.filter(proyecto=proyecto)

                serializer = ProyectoFilesSerializer(archivos, many=True)

                archivos_list = []

                for archivo, serialized_data in zip(archivos, serializer.data):
                    file_url = request.build_absolute_uri(serialized_data['file'])
                    archivo_data = {
                        'id': archivo.id,
                        'string_data': archivo.string_data,
                        'file': file_url,
                        'url_gen' : archivo.url_gen or file_url or archivo.string_data,
                        'filename': archivo.filename,
                        'unit': archivo.unit,
                        'status': archivo.status,
                        'extra': archivo.extra,
                    }
                    archivos_list.append(archivo_data)
                
                img_url = request.build_absolute_uri(ser_pro['img'])

                proyecto_data = {
                    'fecha_creacion': proyecto.fecha_creacion,
                    'uuid': proyecto.uuid,
                    'name': proyecto.name,
                    'descrip': proyecto.desp,
                    'tab':  proyecto.tab, 
                    'img': img_url if proyecto.img else None,
                    'files': archivos_list
                }

                proyectos_list.append(proyecto_data)
            
            return Response(proyectos_list , status=status.HTTP_200_OK)
        else:
            return Response({"msg": "error"}, status=status.HTTP_400_BAD_REQUEST)

    else:
        return Response({'error': 'Method not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

@api_view(['POST'])
def user_proyecto_id(request):
    if request.method == 'POST':
        proj_id = request.GET.get('id')

        username = request.data.get('username', '')
        email = request.data.get('email', '')

        if User.objects.filter(email=email).exists() or User.objects.filter(username=username).exists():
            user_instance = User.objects.filter(email=email).first() or User.objects.filter(username=username).first()
            list_project = Proyecto.objects.filter(uuid=proj_id)

            proyectos_list = []
        
            for proyecto in list_project:
                archivos = ProyectoFiles.objects.filter(proyecto=proyecto)
                
                archivos_list = []

                for archivo in archivos:
                    file_url = request.build_absolute_uri(archivo.file)
                    archivo_data = {
                        'id': archivo.id,
                        'string_data': archivo.string_data,
                        'file': file_url if archivo.file else None,
                        'filename' : archivo.filename ,
                        'unit': archivo.unit,
                        'status' : archivo.status,
                        'extra': archivo.extra,
                    }
                    archivos_list.append(archivo_data)
                
                proyecto_data = {
                    'fecha_creacion': proyecto.fecha_creacion,
                    'uuid': proyecto.uuid,
                    'name': proyecto.name,
                    'descrip': proyecto.desp,
                    'img': proyecto.img.url if proyecto.img else None,
                    'files': archivos_list  
                }

                proyectos_list.append(proyecto_data)
            
            return Response(proyectos_list , status=status.HTTP_200_OK)
        else:
            return Response({"msg": "error"}, status=status.HTTP_400_BAD_REQUEST)

    else:
        return Response({'error': 'Method not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

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

@api_view(['GET', 'POST'])
def xmr_txt(request):
    if request.method == 'GET':
        return Response({'data': 'D'}, status=status.HTTP_201_CREATED)
    elif request.method == 'POST' and request.FILES.get('file'):
        try:
            uploaded_file = request.FILES['file']
            file = UploadFile(file=uploaded_file)
            file.save()

            file_path = file.file.path
            filename_without_extension = splitext(file.file.name)[0].split('/')[-1]

            #path_destino = f'C:\\Users\\NCN\\Documents\\devProject\\python\\restdjango2\\ncnsis\\media\\uploads\\{filename_without_extension}.txt'
            #command = f'copy {file_path} {path_destino}'

            path_destino = f'/var/www/apiqs.ncn.pe/ncnsis/media/uploads/{filename_without_extension}.txt'
            command = f'mr3000-convert {file_path} {path_destino}'

            cmd = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)

            #url = f'http://localhost:8000/media/uploads/{filename_without_extension}.txt'
            url = f'https://apiqs.ncn.pe/media/uploads/{filename_without_extension}.txt'

            return Response(
                {
                 'url' : url,
                }, status=status.HTTP_200_OK)
        except subprocess.CalledProcessError as e:
            return Response({'error': e.output.decode('utf-8')}, status=status.HTTP_400_BAD_REQUEST)
        
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

            unique_filename =  f"GEN_{uuid.uuid4().hex}.mseed"
 
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
            
            try:
                sta_xml = obspy.read_inventory(xml_file)
            except:
                return Response({"error" : 'Formato XML incorrecto'}, status=status.HTTP_406_NOT_ACCEPTABLE)
        
            sens_found = []

            stations_inventory = {f"{net.code}.{sta.code}.{cha.location_code}.{cha.code}" 
                                for net in sta_xml for sta in net for cha in sta}
           
            stations_mseed = {f"{strs.stats.network}.{strs.stats.station}.{strs.stats.location}.{strs.stats.channel}" 
                            for strs in sta_mseed}

            common_stations = stations_inventory.intersection(stations_mseed)

            for station in common_stations:
                for net in sta_xml:
                    for sta in net:
                        for cha in sta:
                            if f"{net.code}.{sta.code}.{cha.location_code}.{cha.code}" == station:
                                sens_found.append({
                                    "station": f'{net.code}.{sta.code}.{cha.location_code}.{cha.code}',
                                    "calib": 1 / cha.response.instrument_sensitivity.value,
                                    "unit": cha.response.instrument_sensitivity.input_units
                                })
                                break  
                        else:
                            continue
                        break
            unit = ''

            while len(sens_found) > 0:
                if sens_found[0]['unit'] == 'M/S**2':
                    unit = 'm'
                    break
                elif sens_found[0]['unit'] == 'CM/S**2':
                    unit= 'cm'
                    break
                elif sens_found[0]['unit'] == 'G':
                    unit= 'g'
                    break
                else:
                    unit = ''
                    break
            
            if len(sens_found) == 0:
                return Response({"error" : 'No se encontraron similitudes con las Estaciones'}, status=status.HTTP_406_NOT_ACCEPTABLE)

            try:
                sta_invSta = sta_xml.select(station=sta_mseed[0].stats.station)
                sta_mseed.attach_response(sta_invSta)
                sta_mseed.remove_sensitivity()
            except:
                d = ''

            unique_filename =  f"GEN_{uuid.uuid4().hex}.mseed"
 
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                sta_mseed.write(temp_file.name, format="MSEED")

                nuevo_archivo = UploadFile()
                nuevo_archivo.file.save(unique_filename, temp_file)
                nuevo_archivo.save()

                serializer = FileUploadSerializer(nuevo_archivo)

            os.unlink(temp_file.name)

            file_url = request.build_absolute_uri(serializer.data['file'])

            return Response({'url':file_url, 'unit': unit, 'xmlData': sens_found}, status=status.HTTP_201_CREATED)
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
        convert_from_unit = request.data.get('unit_from', '')
        convert_to_unit = request.data.get('unit_to', '')

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
                print('')

        except Exception as e:
            return Response({'error': f'Error => {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)
        
        station_full_name = ''

        for station in st:

            try:
                if station.stats.kinemetrics_evt.chan_id == channel_data:
                    channel_data = station.stats.channel
                    station_full_name = f'{station.stats.network}.{station.stats.station}.{station.stats.location}.{station.stats.kinemetrics_evt.chan_id}'
            except:
                channel_data = channel_data
                station_full_name = f'{station.stats.network}.{station.stats.station}.{station.stats.location}.{station.stats.channel}'

            if (station.stats.station == station_data and station.stats.channel == channel_data):

                indice_traza = 0

                for i, traza in enumerate(st):
                    if traza.stats.channel == station.stats.channel:
                        indice_traza = i
                        break

                station.detrend('linear')
                station.filter('bandpass', freqmin=0.1,freqmax=25, corners=2, zerophase=True)

                four = station.data
                four = 100 * four

                filename = data_str.split('/')[-1]
                extension = splitext(filename)[1]

                convert_to_unit = 'm'

                if convert_from_unit:
                    if convert_from_unit == 'gal':
                        if convert_to_unit == 'm':
                            four_data = four * station.stats.calib * 0.01
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'gal' or convert_to_unit == '':
                            four_data = four * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'g':
                            four_data = four * station.stats.calib * 0.001019
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                    if convert_from_unit == 'm':
                        if convert_to_unit == 'gal':
                            four_data = four * station.stats.calib * 100
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'm'  or convert_to_unit == '':
                            four_data = four * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'g':
                            four_data = four * station.stats.calib * 0.101972
                            cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                    if convert_from_unit == 'g':
                        if convert_to_unit == 'gal':
                            four_data = four * station.stats.calib * 980.66
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                        if convert_to_unit == 'm':
                            four_data = four * station.stats.calib * 9.8066
                            cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                        if convert_to_unit == 'g' or convert_to_unit == '':
                            four_data = four * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'unk', 'unk'
                    if convert_from_unit == '' or convert_from_unit == 'null':
                            four_data = four * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'unk', 'unk', 'unk'
                    if convert_from_unit == 'mg':
                        if convert_to_unit == 'm':
                            four_data = four * station.stats.calib * 0.0098
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'gal' :
                            four_data = four * station.stats.calib * 0.981
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'g':
                            four_data = four * station.stats.calib * 0.001
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                        if convert_to_unit == 'mg' or convert_to_unit == '':
                            four_data = four * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'mg', 'cm/s', 'cm'
                else:
                    four_data = four * station.stats.calib * 1
                    cuv1, cuv2, cuv3 = '-unk', '-unk', '-unk'
                
                if extension == '.evt':
                    four_data *= 100 

                try:
                    if station.stats.reftek130:
                        tbw = float(station.stats.reftek130.channel_true_bit_weights[indice_traza].split()[0])
                        ch_gain = float(station.stats.reftek130.channel_gain_code[indice_traza])
                        vpu = station.stats.reftek130.channel_sensor_vpu[indice_traza]
                        factor_conver_psc = 1/ (ch_gain*vpu*1000000/(tbw*9.81))
                        four_data *= factor_conver_psc * 100

                except AttributeError:
                    print("")

                fps = station.stats.sampling_rate
                N = four_data.size
                T = 1.0/fps
                band = 1.0/(2.0*T)
                yf1 = np.fft.fft(four_data)
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
        convert_from_unit = request.data.get('unit_from', '')
        convert_to_unit = request.data.get('unit_to', '')

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
            try:
                if station.stats.kinemetrics_evt.chan_id == channel_data:
                    channel_data = station.stats.channel
            except:
                channel_data = channel_data
                
            if (station.stats.station == station_data and station.stats.channel == channel_data):
                
                indice_traza = 0

                for i, traza in enumerate(st):
                    if traza.stats.channel == station.stats.channel:
                        indice_traza = i
                        break

                osc_damping = 0.05
                station.detrend('linear')
                station.filter('bandpass', freqmin=0.1,freqmax=25, corners=2, zerophase=True)

                fps = station.stats.sampling_rate
                T = 1.0/fps

                four = station.data

                filename = data_str.split('/')[-1]
                extension = splitext(filename)[1]

                convert_to_unit = 'm'

                if convert_from_unit:
                    if convert_from_unit == 'gal':
                        if convert_to_unit == 'm':
                            four_data = four * station.stats.calib * 0.01
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'gal' or convert_to_unit == '':
                            four_data = four * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'g':
                            four_data = four * station.stats.calib * 0.001019
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                    if convert_from_unit == 'm':
                        if convert_to_unit == 'gal':
                            four_data = four * station.stats.calib * 100
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'm'  or convert_to_unit == '':
                            four_data = four * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'g':
                            four_data = four * station.stats.calib * 0.101972
                            cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                    if convert_from_unit == 'g':
                        if convert_to_unit == 'gal':
                            four_data = four * station.stats.calib * 980.66
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                        if convert_to_unit == 'm':
                            four_data = four * station.stats.calib * 9.8066
                            cuv1, cuv2, cuv3 = 'G', 'm/s', 'm'
                        if convert_to_unit == 'g' or convert_to_unit == '':
                            four_data = four * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'G', 'unk', 'unk'
                    if convert_from_unit == '' or convert_from_unit == 'null':
                            four_data = four * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'unk', 'unk', 'unk'
                    if convert_from_unit == 'mg':
                        if convert_to_unit == 'm':
                            four_data = four * station.stats.calib * 0.0098
                            cuv1, cuv2, cuv3 = 'm/s2', 'm/s', 'm'
                        if convert_to_unit == 'gal' :
                            four_data = four * station.stats.calib * 0.981
                            cuv1, cuv2, cuv3 = 'cm/s2', 'cm/s', 'cm'
                        if convert_to_unit == 'g':
                            four_data = four * station.stats.calib * 0.001
                            cuv1, cuv2, cuv3 = 'G', 'cm/s', 'cm'
                        if convert_to_unit == 'mg' or convert_to_unit == '':
                            four_data = four * station.stats.calib * 1
                            cuv1, cuv2, cuv3 = 'mg', 'cm/s', 'cm'
                else:
                    four_data = four * station.stats.calib * 1
                    cuv1, cuv2, cuv3 = '-unk', '-unk', '-unk'
                
                if extension == '.evt':
                    four_data *= 100 

                try:
                    if station.stats.reftek130:
                        tbw = float(station.stats.reftek130.channel_true_bit_weights[indice_traza].split()[0])
                        ch_gain = float(station.stats.reftek130.channel_gain_code[indice_traza])
                        vpu = station.stats.reftek130.channel_sensor_vpu[indice_traza]
                        factor_conver_psc = 1/ (ch_gain*vpu*1000000/(tbw*9.81))
                        four_data *= factor_conver_psc * 100

                except AttributeError:
                    print("")

                
                accels = (1000.0/980.0) * four    

                escalax = np.logspace(-2,1,100)

                osc_freqs = 1.0/escalax
                res_spec = pyrotd.calc_spec_accels(T, accels, osc_freqs, osc_damping)


        return Response({'periodo': escalax, "amplitud": res_spec.spec_accel}, status=status.HTTP_201_CREATED)

# ----------- UTILS --------------------
      
def extract_tr_info(sts):
        tr_info = []
        for tr in sts:
            channel = ''
            
            try: 
                if tr.stats.kinemetrics_evt:
                    channel = tr.stats.kinemetrics_evt.chan_id
            except:
                channel = tr.stats.channel

            tr_info.append({
                'network': tr.stats.network,
                'station': tr.stats.station,
                'location': tr.stats.location,
                'channel': channel,
                'starttime': str(tr.stats.starttime),
                'endtime': str(tr.stats.endtime),
                'sampling_rate': tr.stats.sampling_rate,
                'delta': tr.stats.delta,
                'npts': tr.stats.npts,
                'calib': tr.stats.calib,
                'format': tr.stats._format,
            })
        return tr_info

def read_inventory_safe(data_str):
    try:
        return read_inventory(data_str)
    except Exception:
        return None

def combine_tr_and_inv_info(tr_info, inventory):
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

def orientacion(txt):
    var = txt[-1]
    direccion = ''
    if var == 'Z':
        direccion = "UD"
    if var == 'N':
        direccion = "NS"
    if var == 'E':
        direccion = "EO"
    direccion = txt[:-3]+direccion
    return direccion

def format_value(value):
    if isinstance(value, float):
        if abs(value) < 0.001:
            return format(value, '.2e')
        else:
            return format(value, '.3f')
    return format(value, '.3f')
# -------------------------------------