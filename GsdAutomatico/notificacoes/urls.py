from django.urls import path
from . import views

app_name = 'notificacoes'

urlpatterns = [
    path('api/',        views.api_notificacoes, name='api'),
    path('api/limpar/', views.api_limpar,        name='api_limpar'),
]
