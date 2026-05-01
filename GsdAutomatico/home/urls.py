from django.urls import path
from . import views

app_name = 'home'

urlpatterns = [
    path('', views.HomeDashboardView.as_view(), name='index'),
    path('inbox/', views.HomeInboxView.as_view(), name='inbox'),
    path('tutoriais/', views.TutorialListView.as_view(), name='tutorial_list'),
    path('perfil/', views.ProfileEditView.as_view(), name='profile_edit'),
    path('tutorial/novo/', views.TutorialCreateView.as_view(), name='tutorial_create'),
    path('tutorial/<int:pk>/', views.TutorialDetailView.as_view(), name='tutorial_detail'),
    path('tutorial/<int:pk>/editar/', views.TutorialUpdateView.as_view(), name='tutorial_update'),
    path('tutorial/<int:pk>/deletar/', views.TutorialDeleteView.as_view(), name='tutorial_delete'),
    path('carrossel/', views.CarouselManageView.as_view(), name='carousel_manage'),
    path('tutorial/<int:pk>/imagem/adicionar/', views.TutorialImageAddView.as_view(), name='tutorial_image_add'),
    path('tutorial/<int:pk>/anexo/adicionar/', views.TutorialAttachmentAddView.as_view(), name='tutorial_attachment_add'),
    path('anexo/<int:pk>/deletar/', views.TutorialAttachmentDeleteView.as_view(), name='attachment_delete'),
    path('imagem/<int:pk>/deletar/', views.TutorialImageDeleteView.as_view(), name='image_delete'),
    path('carrossel/<int:pk>/deletar/', views.CarouselSlideDeleteView.as_view(), name='carousel_slide_delete'),
]
