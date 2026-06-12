from django.urls import path
from . import views

app_name = 'SCIM'

urlpatterns = [
    path('', views.IndexSCIM.as_view(), name='index'),
    path('efetivo/', views.EfetivoComCursosListView.as_view(), name='efetivo_list'),
    path('efetivo/<int:pk>/cursos/', views.CursosPorEfetivoView.as_view(), name='efetivo_cursos'),
    path('cursos/', views.CursoEfetivoListView.as_view(), name='curso_list'),
    path('cursos/novo/', views.CursoEfetivoCreateView.as_view(), name='curso_create'),
    path('cursos/<int:pk>/editar/', views.CursoEfetivoUpdateView.as_view(), name='curso_update'),
    path('cursos/<int:pk>/excluir/', views.CursoEfetivoDeleteView.as_view(), name='curso_delete'),
    path('tipos/', views.TipoCursoListView.as_view(), name='tipo_list'),
    path('tipos/novo/', views.TipoCursoCreateView.as_view(), name='tipo_create'),
    path('tipos/<int:pk>/editar/', views.TipoCursoUpdateView.as_view(), name='tipo_update'),
    path('api/efetivos/', views.buscar_efetivos, name='api_efetivos'),
]
