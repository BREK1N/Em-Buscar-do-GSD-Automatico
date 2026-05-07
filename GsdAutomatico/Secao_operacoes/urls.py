from django.urls import path
from . import views

app_name = 'Secao_operacoes'

urlpatterns = [
    path('', views.index, name='index'),

    # Escalas
    path('escalas/', views.escala_list, name='escala_list'),
    path('escalas/nova/', views.escala_create, name='escala_create'),
    path('escalas/<int:pk>/', views.escala_detail, name='escala_detail'),
    path('escalas/<int:pk>/editar/', views.escala_edit, name='escala_edit'),
    path('escalas/<int:pk>/excluir/', views.escala_delete, name='escala_delete'),
    path('escalas/<int:pk>/toggle-ativo/', views.escala_toggle_ativo, name='escala_toggle_ativo'),
    path('escalas/turnos/<int:pk>/remover/', views.turno_delete, name='turno_delete'),
    path('escalas/<int:pk>/turnos/remover-todos/', views.turno_delete_all, name='turno_delete_all'),
    path('escalas/<int:escala_pk>/postos/adicionar/', views.posto_create, name='posto_create'),
    path('escalas/postos/<int:pk>/remover/', views.posto_delete, name='posto_delete'),
    path('escalas/api/eventos/<int:pk>/', views.api_escala_eventos, name='api_escala_eventos'),

    # Missões (OMIS)
    path('missoes/', views.missao_list, name='missao_list'),
    path('missoes/nova/', views.missao_create, name='missao_create'),
    path('missoes/<int:pk>/', views.missao_detail, name='missao_detail'),
    path('missoes/<int:pk>/editar/', views.missao_edit, name='missao_edit'),
    path('missoes/<int:pk>/excluir/', views.missao_delete, name='missao_delete'),
    path('missoes/<int:pk>/pdf/', views.missao_pdf, name='missao_pdf'),
    path('missoes/extrato/pdf/', views.extrato_missao_pdf, name='extrato_missao_pdf'),

    # API missão busca
    path('missoes/api/busca/', views.missao_busca_json, name='missao_busca_json'),
    path('missoes/api/conflitos/', views.militar_conflitos_json, name='militar_conflitos_json'),
    path('api/efetivo/', views.efetivo_busca_json, name='efetivo_busca_json'),

    # Catálogo de equipamentos
    path('equipamentos/catalogo/', views.equipamento_catalogo_list, name='equipamento_catalogo_list'),
    path('equipamentos/catalogo/json/', views.equipamento_catalogo_json, name='equipamento_catalogo_json'),
    path('equipamentos/catalogo/add/', views.equipamento_catalogo_add, name='equipamento_catalogo_add'),
    path('equipamentos/catalogo/<int:pk>/excluir/', views.equipamento_catalogo_delete, name='equipamento_catalogo_delete'),

    # Catálogo de rádios
    path('radios/catalogo/', views.radio_catalogo_list, name='radio_catalogo_list'),
    path('radios/catalogo/json/', views.radio_catalogo_json, name='radio_catalogo_json'),
    path('radios/catalogo/add/', views.radio_catalogo_add, name='radio_catalogo_add'),
    path('radios/catalogo/<int:pk>/excluir/', views.radio_catalogo_delete, name='radio_catalogo_delete'),

    # Catálogo de uniformes
    path('uniformes/catalogo/', views.uniforme_catalogo_list, name='uniforme_catalogo_list'),
    path('uniformes/catalogo/json/', views.uniforme_catalogo_json, name='uniforme_catalogo_json'),
    path('uniformes/catalogo/add/', views.uniforme_catalogo_add, name='uniforme_catalogo_add'),
    path('uniformes/catalogo/<int:pk>/excluir/', views.uniforme_catalogo_delete, name='uniforme_catalogo_delete'),

    # Catálogo de armamentos
    path('armamentos/catalogo/', views.armamento_catalogo_list, name='armamento_catalogo_list'),
    path('armamentos/catalogo/json/', views.armamento_catalogo_json, name='armamento_catalogo_json'),
    path('armamentos/catalogo/add/', views.armamento_catalogo_add, name='armamento_catalogo_add'),
    path('armamentos/catalogo/<int:pk>/excluir/', views.armamento_catalogo_delete, name='armamento_catalogo_delete'),

    # Configuração (admin)
    path('configuracao/', views.config_operacoes, name='config_operacoes'),
]
