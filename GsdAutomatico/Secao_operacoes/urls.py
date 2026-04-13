from django.urls import path
from . import views

app_name = 'Secao_operacoes'

urlpatterns = [
    path('', views.index, name='index'),  
    path('escalas/', views.escala_list, name='escala_list'),
    path('escalas/nova/', views.escala_create, name='escala_create'),
    path('escalas/<int:pk>/', views.escala_detail, name='escala_detail'),
    path('escalas/<int:pk>/editar/', views.escala_edit, name='escala_edit'),
    path('escalas/turnos/<int:pk>/remover/', views.turno_delete, name='turno_delete'),
    path('escalas/<int:pk>/turnos/remover-todos/', views.turno_delete_all, name='turno_delete_all'),
    path('escalas/api/eventos/<int:pk>/', views.api_escala_eventos, name='api_escala_eventos'),
]