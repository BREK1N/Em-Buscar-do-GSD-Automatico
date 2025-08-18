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

    # CONFIGURAÇÃO DE ASSINATURAS
    path('config/oficiais/', views.lista_oficiais, name='lista_oficiais'),
    path('militar/<int:pk>/salvar_assinatura_padrao/', views.salvar_assinatura_padrao, name='salvar_assinatura_padrao'),
]
