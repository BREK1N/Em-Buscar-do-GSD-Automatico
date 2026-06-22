from django.urls import path, include
from . import views

app_name = 'Secao_pessoal'

urlpatterns = [
    path('', views.index, name='index'),
    path('painel-chefe/', views.painel_chefe, name='painel_chefe'),
    path('efetivo/', views.MilitarListView.as_view(), name='militar_list'),
    path('efetivo/adicionar/', views.MilitarCreateView.as_view(), name='militar_create'),
    path('efetivo/<int:pk>/editar/', views.MilitarUpdateView.as_view(), name='militar_update'),
    path('efetivo/<int:pk>/excluir/', views.MilitarDeleteView.as_view(), name='militar_delete'),
    path('efetivo/lixeira/', views.MilitarTrashListView.as_view(), name='militar_trash_list'),
    path('efetivo/lixeira/<int:pk>/restaurar/', views.militar_restore, name='militar_restore'),
    path('efetivo/lixeira/<int:pk>/excluir-permanente/', views.militar_permanently_delete, name='militar_permanently_delete'),
    path('efetivo/lixeira/esvaziar/', views.militar_lixeira_esvaziar, name='militar_lixeira_esvaziar'),
    path('efetivo/importar/', views.importar_excel, name='importar_excel'),
    path('efetivo/baixados/', views.MilitarBaixadoListView.as_view(), name='militar_baixado_list'),
    path('efetivo/<int:pk>/reintegrar/', views.reintegrar_militar, name='reintegrar_militar'),
    path('efetivo/exportar/', views.exportar_efetivo, name='exportar_excel'),
    path('efetivo/<int:pk>/ficha-desimpedimento/', views.gerar_ficha_desimpedimento, name='gerar_ficha_desimpedimento'),
    path('ferramentas/nome-de-guerra/', views.nome_de_guerra, name='nome_de_guerra'),
    path('controle/troca-de-setor/', views.troca_de_setor, name='troca_de_setor'),
    path('controle/troca-de-setor/<int:solicitacao_id>/<str:acao>/', views.responder_troca_setor, name='responder_troca_setor'),
    path('controle/ata/', views.ata, name='ata'),
    path('controle/baixa/', views.baixa, name='baixa'),
    path('controle/movimentacao/', views.movimentar_militar, name='movimentar_militar'),
    path('controle/movimentados/', views.MilitarMovimentadoListView.as_view(), name='militar_movimentado_list'),
    path('controle/indisponiveis/', views.indisponiveis, name='indisponiveis'),
    path('controle/prestacao-servico/', views.PrestacaoServicoListView.as_view(), name='prestacao_servico'),
    path('controle/importar-fq/', views.importar_fq, name='importar_fq'),
    path('controle/tlp/', views.relatorio_tlp, name='relatorio_tlp'),
    path('controle/tlp/lotacoes/', views.LotacaoPessoalListView.as_view(), name='lotacao_list'),
    path('controle/tlp/lotacoes/adicionar/', views.LotacaoPessoalCreateView.as_view(), name='lotacao_create'),
    path('controle/tlp/lotacoes/<int:pk>/editar/', views.LotacaoPessoalUpdateView.as_view(), name='lotacao_update'),
    path('controle/tlp/lotacoes/<int:pk>/excluir/', views.LotacaoPessoalDeleteView.as_view(), name='lotacao_delete'),
    path('gerenciar-opcoes/', views.gerenciar_opcoes, name='gerenciar_opcoes'),
    # Caixa de entrada movida para o app caixa_entrada — /comunicacoes/
    path('ferramentas/comunicacoes/', views.comunicacoes, name='comunicacoes'),  # redireciona
    path('inspsau/', views.inspsau, name='inspsau'),
    path('inspsau/historico/', views.HistoricoInspsauListView.as_view(), name='historico_inspsau_list'),
    path('api/search-militares/', views.api_search_militares, name='api_search_militares'),
    path('inspsau/historico/delete/<int:pk>/', views.historico_inspsau_delete, name='historico_inspsau_delete'),
    path('controle/desercao/', views.desercao, name='desercao'),
]