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
# router.register(r'users', views.UserViewSet)
# router.register(r'groups', views.GroupViewSet)
# router.register(r'seismic_data', views.SeismicDataViewSet, basename='seismic_data')
#router.register(r'upload',views.FileUploadView, basename='file_upload')
#router.register(r'plot',views.PlotFileView, basename='plot')

# router.register(r'trace_data', views.TracesDataView, basename='trace_data')
# router.register(r'trace_baseline_data', views.TracesDataBaseLineView, basename='trace_baseline_data')
# router.register(r'trace_filter_data', views.TracesDataFilterView, basename='trace_filter_data')
# router.register(r'trace_trim_data', views.TracesTrimView, basename='trace_trim_data')

#router.register(r'proyecto', views.ProyectoView, basename='proyecto' )
#router.register(r'files', views.FilesViewSet, basename='files')
#router.register(r'file_info', views.FileInfoViewSet, basename='files_info')
#router.register(r'stationInfo', views.StationInfoViewSet, basename='stationInfo')
#router.register(r'traces', views.TracesListViewSet, basename='traces')

#router.register(r'user-list', views.RegisterUserListView, basename='user-list' )
#router.register(r'proyecto-list', views.ProyectoListView, basename='proyecto-list')
#router.register(r'files-list', views.FilesListViewSet, basename='files-list')
#router.register(r'filesInfo-list', views.FileInfoListViewSet, basename='filesInfo-list')
#router.register(r'stationInfo-list', views.StationInfoListViewSet, basename='stationInfo-list')

#router.register(r'convert-unit', views.ConvertionDataView, basename='Conversor')

#router.register(r'test', views.TestSendData, basename='Test')
#router.register(r'convert_stream', views.ConvertToStream, basename='Stream')
#router.register(r'auto-adjust', views.AutoAdjustView, basename='Auto Ajuste')

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
 
urlpatterns = [
    path('', include(router.urls)),
    # path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
    
    # path('options/', views.options_view),
    # path('proyecto/buscar/<str:uuid>', views.getProyectoView.as_view({'get': 'buscar_proyecto'}), name='buscar-proyecto'),
    # path('proyectoUser/buscar/<str:uuid>', views.getUserProjectsView.as_view({'get': 'buscar_user_proyecto'}), name='buscar'),
    # path('snippets/', views.snippet_list),

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
    
    #path('api-token-auth/', views.CustomAuthToken.as_view()),
    #path('ap/users/', views.ListUser.as_view())
]

urlpatterns += router.urls 

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)