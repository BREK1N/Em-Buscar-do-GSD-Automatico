# informatica/urls.py
from django.urls import path
from . import views

app_name = 'informatica'

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard, name='dashboard'),

    # URLs para Utilizador (User)
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/add/', views.UserCreateView.as_view(), name='user_add'),
    path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    path('users/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
    path('users/<int:pk>/reset-password/', views.reset_user_password, name='user_reset_password'),

    # URLs para Grupos de Permissão
    path('groups/', views.GroupListView.as_view(), name='group_list'),
    path('groups/add/', views.GroupCreateView.as_view(), name='group_add'),
    path('groups/<int:pk>/edit/', views.GroupUpdateView.as_view(), name='group_edit'),
    path('groups/<int:pk>/delete/', views.GroupDeleteView.as_view(), name='group_delete'),

    # URL para Configuração
    path('configuracao/', views.ConfiguracaoUpdateView.as_view(), name='configuracao_edit'),

    # ===============================================
    # URLS GESTÃO DE MATERIAIS E CAUTELAS
    # ===============================================
    path('gestao-materiais/', views.gestao_materiais_view, name='gestao_materiais'),
    path('api/materiais/add-grupo/', views.api_add_grupo, name='api_add_grupo'),
    path('api/materiais/add-subgrupo/', views.api_add_subgrupo, name='api_add_subgrupo'),
    
    # Material: Criar, Editar, Excluir
    path('api/materiais/add-material/', views.api_add_material, name='api_add_material'),
    path('api/materiais/edit-material/<int:pk>/', views.api_edit_material, name='api_edit_material'),
    path('api/materiais/delete-material/<int:pk>/', views.api_delete_material, name='api_delete_material'),
    
    path('api/materiais/delete-grupo/<int:pk>/', views.api_delete_grupo, name='api_delete_grupo'),
    path('api/materiais/delete-subgrupo/<int:pk>/', views.api_delete_subgrupo, name='api_delete_subgrupo'),
    
    path('api/cautelas/salvar/', views.api_salvar_cautela, name='api_salvar_cautela'),
    path('api/cautelas/<int:pk>/devolver/', views.api_devolver_cautela, name='api_devolver_cautela'),
    path('api/cautelas/item/<int:item_id>/devolver/', views.api_devolver_item_cautela, name='api_devolver_item_cautela'),
    path('api/cautelas/<int:cautela_id>/devolver-multiplos/', views.api_devolver_multiplos_itens, name='api_devolver_multiplos_itens'),
    path('api/cautelas/<int:cautela_id>/add-item/', views.api_add_item_cautela, name='api_add_item_cautela'),
    
    path('cautelas/<int:pk>/imprimir/', views.imprimir_cautela, name='imprimir_cautela'),

    # APIs para Armários e Prateleiras (Restauradas)
    path('api/armarios/add/', views.api_add_armario, name='api_add_armario'),
    path('api/armarios/edit/<int:pk>/', views.api_edit_armario, name='api_edit_armario'),
    path('api/armarios/delete/<int:pk>/', views.api_delete_armario, name='api_delete_armario'),
    
    path('api/prateleiras/add/', views.api_add_prateleira, name='api_add_prateleira'),
    path('api/prateleiras/edit/<int:pk>/', views.api_edit_prateleira, name='api_edit_prateleira'),
    path('api/prateleiras/delete/<int:pk>/', views.api_delete_prateleira, name='api_delete_prateleira'),

    # Exportação de Armários para Excel
    path('api/armarios/exportar/', views.exportar_armarios_excel, name='exportar_armarios_excel'),

    # ===============================================
    # INFRAESTRUTURA E LOGS
    # ===============================================
    path('api/logs/', views.system_logs_api, name='system_logs_api'),
    path('monitoramento/', views.monitoramento_backup, name='monitoramento_backup'),
    path('logs-backup/', views.visualizar_logs_backup, name='logs_backup'),
]