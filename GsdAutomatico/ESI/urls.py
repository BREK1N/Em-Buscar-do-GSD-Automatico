from django.urls import path
from . import views

app_name = 'ESI'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('missoes/', views.painel_missoes, name='painel_missoes'),
    path('missoes/<int:missao_id>/escala/', views.missao_escala, name='missao_escala'),
    path('missoes/<int:missao_id>/escala/salvar/', views.salvar_escala, name='salvar_escala'),
    path('missoes/<int:missao_id>/escala/pdf/', views.missao_escala_pdf, name='escala_pdf'),
    path('missoes/compilado/pdf/', views.compilado_esi_pdf, name='compilado_esi_pdf'),
    path('api/missoes/<int:missao_id>/status/', views.api_escala_status, name='api_escala_status'),
    path('api/missoes/<int:missao_id>/conflitos/<int:militar_id>/', views.api_conflitos_militar, name='api_conflitos_militar'),
]
