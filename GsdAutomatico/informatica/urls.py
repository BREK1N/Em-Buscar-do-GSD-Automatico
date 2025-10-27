# informatica/urls.py
from django.urls import path
from . import views # Supondo que as views serão criadas aqui

app_name = 'informatica'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Descomente estas linhas
    path('militares/', views.MilitarListView.as_view(), name='militar_list'),
    path('militares/add/', views.MilitarCreateView.as_view(), name='militar_add'),
    path('militares/<int:pk>/edit/', views.MilitarUpdateView.as_view(), name='militar_edit'),
    path('militares/<int:pk>/delete/', views.MilitarDeleteView.as_view(), name='militar_delete'),

    # path('users/', views.UserListView.as_view(), name='user_list'),
    # path('users/add/', views.UserCreateView.as_view(), name='user_add'),
    # path('users/<int:pk>/edit/', views.UserUpdateView.as_view(), name='user_edit'),
    # path('users/<int:pk>/delete/', views.UserDeleteView.as_view(), name='user_delete'),
]