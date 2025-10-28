# GsdAutomatico/login/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import CustomUserCreationForm, CustomSetPasswordForm
from django.contrib import messages
from django.urls import reverse # Importar reverse

def is_admin(user):
    return user.is_superuser

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

# --- NOVA FUNÇÃO AUXILIAR ---
def redirect_based_on_groups(user):
    """
    Determina para onde redirecionar o utilizador com base nos seus grupos.
    """
    app_groups = {
        'Ouvidoria': 'Ouvidoria:index',
        'Informatica': 'informatica:dashboard',
        # Adicione outros mapeamentos grupo -> URL aqui
    }
    user_groups = user.groups.values_list('name', flat=True)

    accessible_apps = []
    for group_name, url_name in app_groups.items():
        if group_name in user_groups:
            accessible_apps.append(url_name)

    # Superutilizadores têm acesso a tudo por padrão
    if user.is_superuser:
        # Se houver apps definidos, mostra a seleção, senão vai para o admin
        if app_groups:
             # Um superuser pode ter acesso implícito, vamos listar todos os apps definidos
             accessible_apps = list(app_groups.values())
             if len(accessible_apps) > 1:
                 return redirect('login:select_app')
             elif len(accessible_apps) == 1:
                 return redirect(accessible_apps[0])
             else: # Se não houver apps mapeados, vai para o admin
                 return redirect('/admin/')
        else:
            return redirect('/admin/') # Superuser sem apps definidos vai para admin

    # Lógica para utilizadores normais
    if len(accessible_apps) == 1:
        # Pertence a exatamente um grupo de app
        return redirect(accessible_apps[0])
    elif len(accessible_apps) > 1:
        # Pertence a múltiplos grupos de app
        return redirect('login:select_app')
    else:
        # Não pertence a nenhum grupo de app específico
        if user.is_staff:
            # Se for staff (mas não superuser), pode ir para o admin
            return redirect('/admin/')
        else:
            # Fallback para utilizadores sem grupo e não staff (pode ajustar)
            # É necessário passar o request para messages.warning
            # Como esta função não recebe request, vamos retornar um URL
            # e a view que chamar esta função pode adicionar a mensagem.
            # Idealmente, a lógica de mensagens seria movida para a view principal.
            # Por agora, apenas redireciona para o login.
            return redirect('login:login') # Ou outra página padrão

# --- NOVA VIEW PARA SELEÇÃO DE APP ---
@login_required
def select_app_view(request):
    """
    Mostra uma página para o utilizador escolher qual app aceder.
    """
    app_groups = {
        'Ouvidoria': {'url_name': 'Ouvidoria:index', 'display_name': 'Ouvidoria GSD'},
        'Informatica': {'url_name': 'informatica:dashboard', 'display_name': 'Dashboard Informática'},
        # Adicione outros mapeamentos aqui
    }
    user_groups = request.user.groups.values_list('name', flat=True)

    available_apps = []
    if request.user.is_superuser:
        # Superuser vê todos os apps definidos
        available_apps = list(app_groups.values())
    else:
        for group_name, app_info in app_groups.items():
            if group_name in user_groups:
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
    return redirect('login:login')

def custom_404_view(request, exception):
    """
    Redireciona o utilizador quando uma página não é encontrada.
    - Se estiver logado, vai para a página principal da aplicação (ou seleção).
    - Se não estiver logado, vai para a página de login.
    """
    if request.user.is_authenticated:
        # Usa a mesma lógica de redirecionamento do login
        return redirect_based_on_groups(request.user)
    else:
        return redirect('login:login')