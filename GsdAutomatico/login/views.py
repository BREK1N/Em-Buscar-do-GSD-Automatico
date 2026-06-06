# GsdAutomatico/login/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django_ratelimit.decorators import ratelimit
from GsdAutomatico.ratelimit_utils import rate_if_external
from .forms import CustomUserCreationForm, CustomSetPasswordForm
from django.contrib import messages
from django.urls import reverse

def is_admin(user):
    return user.is_superuser

@ratelimit(key='ip', rate=rate_if_external, method='POST', block=True)
def login_view(request):
    if request.user.is_authenticated:
        # Se já está autenticado, verifica os grupos para redirecionar corretamente
        return redirect_based_on_groups(request.user)

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)

            if user is not None:
                login(request, user)
                if password == '12345678':
                    # Redireciona para troca de senha obrigatória
                    return redirect('login:change_password')
                else:
                    # <<< LÓGICA DE REDIRECIONAMENTO APLICADA AQUI >>>
                    return redirect_based_on_groups(user)
            else:
                messages.error(request,"Utilizador ou palavra-passe inválidos.")
        else:
            messages.error(request,"Utilizador ou palavra-passe inválidos.")

    form = AuthenticationForm()
    return render(request, 'login/login.html', {'form': form})

@login_required # Garante que só utilizadores logados acedam
def home_redirect_view(request):
    return redirect_based_on_groups(request.user)

# --- FUNÇÃO AUXILIAR ---
def redirect_based_on_groups(user):
    """
    Redireciona o utilizador para o portal Home.
    Superuser staff-only sem grupos vai para o admin.
    """
    if user.is_superuser and not user.groups.exists():
        return redirect('/admin/')
    return redirect('home:index')

# --- NOVA VIEW PARA SELEÇÃO DE APP ---
@login_required
def select_app_view(request):
    """
    Mostra uma página para o utilizador escolher qual app aceder.
    """
    from Ouvidoria.permissions import OUVIDORIA_GROUPS
    _ouvidoria_app = {'url_name': 'Ouvidoria:index', 'display_name': 'Ouvidoria GSD'}
    _sop_app = {'url_name': 'Secao_operacoes:index', 'display_name': 'Seção de Operações'}
    app_groups = {
        **{g: _ouvidoria_app for g in OUVIDORIA_GROUPS},
        'informatica-admin': {'url_name': 'informatica:dashboard', 'display_name': 'Dashboard Informática'},
        'informatica-secao': {'url_name': 'informatica:dashboard', 'display_name': 'Dashboard Informática'},
        'Seção de Pessoal (S1)': {'url_name': 'Secao_pessoal:index', 'display_name': 'Seção de Pessoal'},
        'SOP - Operações': _sop_app,
        'SOP- Escalas': _sop_app,
    }
    user_groups = set(request.user.groups.values_list('name', flat=True))

    seen_urls = set()
    available_apps = []
    candidates = app_groups.keys() if request.user.is_superuser else user_groups
    for group_name in candidates:
        app_info = app_groups.get(group_name)
        if app_info and app_info['url_name'] not in seen_urls:
            seen_urls.add(app_info['url_name'])
            available_apps.append(app_info)

    # Se, por algum motivo, o utilizador chegar aqui sem apps disponíveis (não deveria acontecer pela lógica anterior)
    if not available_apps:
         messages.warning(request, "Nenhuma aplicação disponível.")
         # Tenta redirecionar para um fallback seguro
         if request.user.is_staff:
             return redirect('/admin/')
         else:
             logout(request) # Desloga se não tiver para onde ir
             return redirect('login:login')
    # Se só tiver 1 app (ex: superuser com apenas 1 app definido), redireciona direto
    elif len(available_apps) == 1:
        return redirect(available_apps[0]['url_name'])


    context = {
        'available_apps': available_apps
    }
    return render(request, 'login/select_app.html', context)


@login_required
@ratelimit(key='user', rate='5/m', method='POST', block=True)
def force_password_change_view(request):
    if request.method == 'POST':
        form = CustomSetPasswordForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'A sua senha foi alterada com sucesso!')
            # Após trocar a senha, redireciona baseado nos grupos
            return redirect_based_on_groups(user)
    else:
        form = CustomSetPasswordForm(user=request.user)

    # --- CORREÇÃO APLICADA AQUI ---
    # O caminho correto não deve incluir 'templates'
    return render(request, 'login/change_password.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('home:index')

def custom_404_view(request, exception):
    """
    Redireciona o utilizador quando uma página não é encontrada.
    - Se estiver logado, vai para a página principal da aplicação (ou seleção).
    - Se não estiver logado, vai para a página de login.
    """
    if request.user.is_authenticated:
        return redirect_based_on_groups(request.user)
    else:
        return redirect('login:login')


def custom_403_view(request, exception=None):
    from django_ratelimit.exceptions import Ratelimited
    if isinstance(exception, Ratelimited):
        return render(request, 'login/429.html', status=429)
    return render(request, 'login/403.html', status=403)