from django.shortcuts import render
from django.contrib.auth.decorators import login_required

@login_required 
def index(request):
    context = {
        'page_title': 'Dashboard - Seção de Pessoal',
    }
    
    return render(request, 'Secao_pessoal/index.html', context)