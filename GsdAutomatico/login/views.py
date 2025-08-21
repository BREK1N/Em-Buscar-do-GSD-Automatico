from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import CustomUserCreationForm, CustomSetPasswordForm
from django.contrib import messages

def is_admin(user):
    return user.is_superuser

def login_view(request):
    if request.user.is_authenticated:
        return redirect('Ouvidoria:index')

    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                if password == '12345678':
                    return redirect('login:change_password')
                else:
                    return redirect('Ouvidoria:index')
            else:
                messages.error(request,"Utilizador ou palavra-passe inválidos.")
        else:
            messages.error(request,"Utilizador ou palavra-passe inválidos.")
    
    form = AuthenticationForm()
    return render(request, 'login/login.html', {'form': form})

@login_required
def force_password_change_view(request):
    if request.method == 'POST':
        form = CustomSetPasswordForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  
            messages.success(request, 'A sua senha foi alterada com sucesso!')
            return redirect('Ouvidoria:index')
    else:
        form = CustomSetPasswordForm(user=request.user)
    
    # --- CORREÇÃO APLICADA AQUI ---
    # O caminho correto não deve incluir 'templates'
    return render(request, 'login/change_password.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login:login')

@login_required
@user_passes_test(is_admin)
def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Utilizador '{user.username}' criado com sucesso!")
            return redirect('Ouvidoria:index')
        else:
            # ADICIONE ESTA LINHA PARA DEPURAR OS ERROS
            print("ERROS DE VALIDAÇÃO DO FORMULÁRIO:", form.errors.as_json())
    else:
        form = CustomUserCreationForm()
    return render(request, 'login/register.html', {'form': form})

def custom_404_view(request, exception):
    """
    Redireciona o utilizador quando uma página não é encontrada.
    - Se estiver logado, vai para a página principal da aplicação.
    - Se não estiver logado, vai para a página de login.
    """
    if request.user.is_authenticated:
        return redirect('Ouvidoria:index')
    else:
        return redirect('login:login')