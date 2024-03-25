"""
URL configuration for sims project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path
from rest_framework import routers

from restapi import views

router = routers.DefaultRouter()

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
 
urlpatterns = [
    path('', include(router.urls)),
    # path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    
    # path('proyecto/buscar/<str:uuid>', views.getProyectoView.as_view({'get': 'buscar_proyecto'}), name='buscar-proyecto'),
    # path('proyectoUser/buscar/<str:uuid>', views.getUserProjectsView.as_view({'get': 'buscar_user_proyecto'}), name='buscar'),

    path('calibration/', views.mseed_xml),

    path('fourier/', views.create_fourier),
    path('espectro-fourier/', views.create_espectro),

    path('convert/', views.xmr_txt),

    path('upload/', views.upload_file),
    path('seismic_data/', views.station_data),
    path('trace_data/', views.trace_data),

    path('trace_baseline_data/', views.data_process),
    path('trace_filter_data/', views.data_process),
    path('trace_trim_data/', views.data_process),

    path('convert-unit/', views.data_process),
    path('convert_stream/', views.convert_stream),
    path('auto-adjust/', views.auto_adjust),

    path('plot/', views.data_plot),

    path('plot-tool/', views.data_plot_process),
    path('plot-tool-auto/', views.data_plot_auto),

    # -------------------  CONTROL  -----------------------

    path('up-file-l/', views.files_uploaded),

    # --------------- USER ENDPOINTS -----------------------

    path('user/', views.crear_usuario),

    path('upload_user/', views.upload_file_user),

    path('mseed_xml_user/', views.mseed_xml_user),
    path('mseed_list_user/', views.mseed_calib_fact),

    path('new_pro/', views.crear_proyecto),
    path('new_f_pro/', views.file_project),
    path('pro/', views.user_proyecto)


    # ------------- ↑↑ USER ENDPOINTS ↑↑ -----------------------

    #path('api-token-auth/', views.CustomAuthToken.as_view()),
    #path('ap/users/', views.ListUser.as_view())
]

urlpatterns += router.urls 

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)