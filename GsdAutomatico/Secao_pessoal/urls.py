from django.urls import path, include
from . import views

app_name = 'Secao_pessoal'

urlpatterns = [
    path('', views.index, name='index'),
]