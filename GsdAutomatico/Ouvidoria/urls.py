from django.urls import path, include

app_name = 'Ouvidoria'

urlpatterns = [
    path('', include('Ouvidoria.urls')),  
]
