from django.urls import path
from . import views

app_name = 'Secao_operacoes'

urlpatterns = [
    path('', views.index, name='index'),  
]