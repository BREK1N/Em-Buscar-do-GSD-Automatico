from django.urls import path, include
from . import views

app_name = 'Secao_pessoal'

urlpatterns = [
    path('', views.index, name='index'),
    path('efetivo/', views.MilitarListView.as_view(), name='militar_list'),
    path('efetivo/adicionar/', views.MilitarCreateView.as_view(), name='militar_create'),
    path('efetivo/<int:pk>/editar/', views.MilitarUpdateView.as_view(), name='militar_update'),
    path('efetivo/<int:pk>/excluir/', views.MilitarDeleteView.as_view(), name='militar_delete'),
    path('efetivo/importar/', views.importar_excel, name='importar_excel'),
    path('efetivo/baixados/', views.MilitarBaixadoListView.as_view(), name='militar_baixado_list'),
    path('efetivo/<int:pk>/reintegrar/', views.reintegrar_militar, name='reintegrar_militar'),
    path('efetivo/lixeira/', views.MilitarTrashListView.as_view(), name='militar_trash_list'),
    path('efetivo/<int:pk>/restaurar/', views.militar_restore, name='militar_restore'),
    path('efetivo/<int:pk>/excluir-permanente/', views.militar_permanently_delete, name='militar_permanently_delete'),
    path('efetivo/exportar/', views.exportar_efetivo, name='exportar_excel'),
    path('ferramentas/nome-de-guerra/', views.nome_de_guerra, name='nome_de_guerra'),
    path('controle/troca-de-setor/', views.troca_de_setor, name='troca_de_setor'),
    path('controle/troca-de-setor/<int:solicitacao_id>/<str:acao>/', views.responder_troca_setor, name='responder_troca_setor'),
    path('controle/ata/', views.ata, name='ata'),
    path('controle/baixa/', views.baixa, name='baixa'),
    path('controle/indisponiveis/', views.indisponiveis, name='indisponiveis'),
    path('gerenciar-opcoes/', views.gerenciar_opcoes, name='gerenciar_opcoes'),
    path('ferramentas/comunicacoes/', views.comunicacoes, name='comunicacoes'),
    path('ferramentas/comunicacoes/acoes-em-massa/', views.acoes_em_massa_comunicacoes, name='acoes_em_massa_comunicacoes'),
    path('ferramentas/comunicacoes/arquivar/<int:notificacao_id>/', views.arquivar_mensagem, name='arquivar_mensagem'),
    path('ferramentas/comunicacoes/excluir/<int:notificacao_id>/', views.excluir_mensagem, name='excluir_mensagem'),
    path('api/notificacoes/', views.api_notificacoes_check, name='api_notificacoes_check'),
    path('inspsau/', views.inspsau, name='inspsau'),
    path('inspsau/historico/', views.HistoricoInspsauListView.as_view(), name='historico_inspsau_list'),
    path('api/search-militares/', views.api_search_militares, name='api_search_militares'),
    path('inspsau/historico/delete/<int:pk>/', views.historico_inspsau_delete, name='historico_inspsau_delete'),
]

































print