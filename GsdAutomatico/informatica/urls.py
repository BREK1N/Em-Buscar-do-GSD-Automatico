# informatica/urls.py
from django.urls import path
from . import views

app_name = 'informatica'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # URLs para Militar (já existiam)
    path('militares/', views.MilitarListView.as_view(), name='militar_list'),
    path('militares/add/', views.MilitarCreateView.as_view(), name='militar_add'),
    path('militares/<int:pk>/edit/', views.MilitarUpdateView.as_view(), name='militar_edit'),
    path('militares/<int:pk>/delete/', views.MilitarDeleteView.as_view(), name='militar_delete'),

    # URLs para User
    path('users/', views.UserListView.as_view(), name='user_list'),
    path('users/add/', views.UserCreateView.as_view(), name='user_add'),
    path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    path('users/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),

    # URLs para Group
    path('groups/', views.GroupListView.as_view(), name='group_list'),
    path('groups/add/', views.GroupCreateView.as_view(), name='group_add'),
    path('groups/<int:pk>/edit/', views.GroupUpdateView.as_view(), name='group_edit'),
    path('groups/<int:pk>/delete/', views.GroupDeleteView.as_view(), name='group_delete'),

    # URLs para UserProfile (Apenas Lista e Edição)
    path('profiles/', views.UserProfileListView.as_view(), name='userprofile_list'),
    path('profiles/<int:pk>/edit/', views.UserProfileUpdateView.as_view(), name='userprofile_edit'),
    # Não teremos add/delete para profiles diretamente aqui

    # URL para PATD (Apenas Lista)
    path('patds/', views.PATDListView.as_view(), name='patd_list'),

    # URL para Configuracao (Apenas Edição)
    path('configuracao/', views.ConfiguracaoUpdateView.as_view(), name='configuracao_edit'),

]