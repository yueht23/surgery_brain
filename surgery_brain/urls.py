from django.urls import path
from . import views

urlpatterns = [

    path('first_schedule', views.get_first_schedule),
    path('sec_schedule', views.get_sec_schedule),

    # 如下接口只是为了方便测试，实际使用时不需要
    path('reset_info_port', views.reset_info_port),
    path('sync_info_python_to_info', views.sync_info_python_to_info),
    path('gantt_chart', views.gantt_chart),
    path('hello_world', views.hello_world),
]
