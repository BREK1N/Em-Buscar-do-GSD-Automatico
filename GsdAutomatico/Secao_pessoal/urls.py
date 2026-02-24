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
    path('ferramentas/nome-de-guerra/', views.nome_de_guerra, name='nome_de_guerra'),
    path('controle/troca-de-setor/', views.troca_de_setor, name='troca_de_setor'),
    path('gerenciar-opcoes/', views.gerenciar_opcoes, name='gerenciar_opcoes'),
    path('ferramentas/comunicacoes/', views.comunicacoes, name='comunicacoes'),

]