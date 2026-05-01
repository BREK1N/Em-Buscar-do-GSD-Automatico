from django.urls import path
from . import views

app_name = 'chamados'

urlpatterns = [
    path('', views.ChamadoListView.as_view(), name='lista'),
    path('novo/', views.ChamadoCreateView.as_view(), name='novo'),
    path('<int:pk>/', views.ChamadoDetailView.as_view(), name='detalhe'),
    path('<int:pk>/atender/', views.atender_chamado_view, name='atender'),
    path('<int:pk>/reply/', views.reply_chamado_view, name='reply'),
    path('<int:pk>/status/', views.update_status_view, name='status'),
    path('anexo/<int:pk>/', views.download_anexo_view, name='download_anexo'),
]
