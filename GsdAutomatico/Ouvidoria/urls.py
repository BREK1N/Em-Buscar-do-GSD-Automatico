from django.urls import path, include
from . import views

app_name = 'Ouvidoria'

urlpatterns = [
    # Analisador de Transgressões parte principal do projeto index
    path('', views.index, name='index'),  

    # Aba de efetivos
    path('efetivo/', views.MilitarListView.as_view(), name='militar_list'),
    path('efetivo/adicionar/', views.MilitarCreateView.as_view(), name='militar_create'),
    path('efetivo/<int:pk>/editar/', views.MilitarUpdateView.as_view(), name='militar_update'),
    path('efetivo/<int:pk>/excluir/', views.MilitarDeleteView.as_view(), name='militar_delete'),
    path('efetivo/<int:pk>/patds/', views.MilitarPATDListView.as_view(), name='militar_patd_list'),
    path('efetivo/importar/', views.importar_excel, name='importar_excel'),

    # Aba de PATDs
    path('patd/', views.PATDListView.as_view(), name='patd_list'),
    path('patd/<int:pk>/', views.PATDDetailView.as_view(), name='patd_detail'),
    path('patd/<int:pk>/editar/', views.PATDUpdateView.as_view(), name='patd_update'),
    path('patd/<int:pk>/excluir/', views.PATDDeleteView.as_view(), name='patd_delete'),
    path('patd/<int:pk>/salvar_assinatura/', views.salvar_assinatura, name='salvar_assinatura'),
    path('patd/<int:pk>/salvar_documento/', views.salvar_documento_patd, name='salvar_documento_patd'),
    path('patd/<int:pk>/salvar_assinatura_ciencia/', views.salvar_assinatura_ciencia, name='salvar_assinatura_ciencia'),
    path('patd/<int:pk>/salvar_alegacao_defesa/', views.salvar_alegacao_defesa, name='salvar_alegacao_defesa'),
    path('patd/<int:pk>/extender_prazo/', views.extender_prazo, name='extender_prazo'),
    path('patd/<int:pk>/prosseguir_sem_alegacao/', views.prosseguir_sem_alegacao, name='prosseguir_sem_alegacao'), 
    path('patd/<int:pk>/salvar_assinatura_testemunha/<int:testemunha_num>/', views.salvar_assinatura_testemunha, name='salvar_assinatura_testemunha'), 

    # CONFIGURAÇÃO DE ASSINATURAS
    path('config/oficiais/', views.lista_oficiais, name='lista_oficiais'),
    path('militar/<int:pk>/salvar_assinatura_padrao/', views.salvar_assinatura_padrao, name='salvar_assinatura_padrao'),
    path('config/padroes/', views.gerenciar_configuracoes_padrao, name='gerenciar_configuracoes_padrao'),

    # ROTAS PARA NOTIFICAÇÕES (NOVAS)
    path('notificacoes/patds-expirados/', views.patds_expirados_json, name='patds_expirados_json'),
    path('notificacoes/extender-prazo-massa/', views.extender_prazo_massa, name='extender_prazo_massa'),
    path('notificacoes/verificar-prazos/', views.verificar_e_atualizar_prazos, name='verificar_e_atualizar_prazos'),
]
