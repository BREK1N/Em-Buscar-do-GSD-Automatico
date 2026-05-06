from django.urls import path
from . import views

app_name = 'chamada'

urlpatterns = [
    path('', views.chamada_index, name='chamada_index'),
    path('toggle/', views.chamada_toggle, name='chamada_toggle'),
]