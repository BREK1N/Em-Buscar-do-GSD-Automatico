from django.urls import path
from . import views

app_name = 'login'

urlpatterns = [
    path('', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('change-password/', views.force_password_change_view, name='change_password'),
    path('select-app/', views.select_app_view, name='select_app'),
    path('go-home/', views.home_redirect_view, name='go_home'), 
]