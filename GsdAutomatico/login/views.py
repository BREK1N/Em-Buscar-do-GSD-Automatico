from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import CustomUserCreationForm
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
                return redirect('Ouvidoria:index')
            else:
                messages.error(request,"Utilizador ou palavra-passe inválidos.")
        else:
            messages.error(request,"Utilizador ou palavra-passe inválidos.")
    form = AuthenticationForm()
    return render(request, 'login/login.html', {'form': form})

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
        form = CustomUserCreationForm()
    return render(request, 'login/register.html', {'form': form})
