from django.urls import path
from . import views

app_name = 'caixa_entrada'

urlpatterns = [
    # Caixa de entrada principal
    path('', views.InboxListView.as_view(), name='inbox'),
    path('enviados/', views.EnviadosListView.as_view(), name='enviados'),
    path('rascunhos/', views.RascunhosListView.as_view(), name='rascunhos'),
    path('excluidos/', views.ExcluidosListView.as_view(), name='excluidos'),
    path('favoritos/', views.FavoritosListView.as_view(), name='favoritos'),

    # Escrever / editar rascunho
    path('nova/', views.EscreveView.as_view(), name='nova'),
    path('nova/<int:pk>/', views.EscreveView.as_view(), name='editar_rascunho'),

    # Detalhe
    path('<int:pk>/', views.DetalheView.as_view(), name='detalhe'),

    # Ações sobre mensagens
    path('<int:pk>/excluir/', views.excluir_mensagem_view, name='excluir'),
    path('<int:pk>/excluir-definitivo/', views.excluir_definitivo_view, name='excluir_definitivo'),
    path('<int:pk>/restaurar/', views.restaurar_mensagem_view, name='restaurar'),
    path('<int:pk>/favoritar/', views.favoritar_mensagem_view, name='favoritar'),
    path('<int:pk>/marcar-lida/', views.marcar_lida_view, name='marcar_lida'),
    path('lote/', views.excluir_lote_view, name='excluir_lote'),

    # Chamados (admin)
    path('chamados/', views.ChamadoListView.as_view(), name='chamados'),
    path('chamados/<int:pk>/status/', views.chamado_update_status, name='chamado_status'),

    # Anexos
    path('anexo/<int:pk>/', views.download_anexo, name='download_anexo'),

    # APIs
    path('api/check/', views.api_notificacoes_check, name='api_check'),
    path('api/usuarios/', views.api_buscar_usuarios, name='api_usuarios'),

    # Compatibilidade legada
    path('inbox/', views.comunicacoes, name='comunicacoes'),
]
