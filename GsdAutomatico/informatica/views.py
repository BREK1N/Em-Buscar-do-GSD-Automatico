# GsdAutomatico/informatica/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.apps import apps
from django.urls import reverse, NoReverseMatch, reverse_lazy
from django.contrib.auth.models import User, Group
from Ouvidoria.models import Militar, PATD, Anexo, Configuracao
from login.models import UserProfile
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .forms import (
    MilitarForm, InformaticaUserCreationForm, InformaticaUserChangeForm,
    GroupForm, UserProfileForm, ConfiguracaoForm
)
from django.db.models import Q
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages

# --- Imports Adicionados para os Logs do Docker ---
import datetime
import docker
# --------------------------------------------------

logger = logging.getLogger(__name__)

# Função helper para verificar se é staff
def is_staff(user):
    return user.is_staff

class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = reverse_lazy('login:login')
    def test_func(self):
        return is_staff(self.request.user)

    def handle_no_permission(self):
        return super().handle_no_permission()

# --- View do Dashboard (Atualizada) ---
@staff_member_required
def dashboard(request):
    general_models_info = [
        ('auth', 'user', 'Utilizadores', 'Utilizador'),
        ('auth', 'group', 'Grupos de Permissão', 'Grupo'),
    ]
    
    ouvidoria_models_info = [
        ('Ouvidoria', 'militar', 'Efetivo (Militares)', 'Militar'),
        ('Ouvidoria', 'patd', 'Processos (PATD)', 'PATD'),
        ('Ouvidoria', 'configuracao', 'Configurações Gerais', 'Configuração'),
    ]

    def get_model_admin_links(model_info_list):
        processed_list = []
        for app_label, model_name, plural_name, singular_name in model_info_list:
            item_data = {
                'name': plural_name, 'singular': singular_name, 'model_name': model_name,
                'list_url': '#', 'add_url': '#', 'edit_config_url': '#', 'count': None
            }
            try:
                model = apps.get_model(app_label, model_name)
                list_url_name = f'informatica:{model_name}_list'
                add_url_name = f'informatica:{model_name}_add'
                edit_config_url_name = f'informatica:configuracao_edit'

                if model_name == 'configuracao':
                    try:
                        item_data['edit_config_url'] = reverse(edit_config_url_name)
                        item_data['list_url'] = item_data['edit_config_url']
                        item_data['add_url'] = item_data['edit_config_url']
                    except NoReverseMatch:
                        logger.warning(f"URL '{edit_config_url_name}' ainda não definida.")
                else:
                    try: item_data['list_url'] = reverse(list_url_name)
                    except NoReverseMatch: logger.warning(f"URL '{list_url_name}' ainda não definida.")
                    try: item_data['add_url'] = reverse(add_url_name)
                    except NoReverseMatch: logger.warning(f"URL '{add_url_name}' ainda não definida.")
                    item_data['count'] = model.objects.count()

                processed_list.append(item_data)
            except LookupError: logger.warning(f"Modelo {app_label}.{model_name} não encontrado.")
            except Exception as e: logger.error(f"Erro ao processar modelo {app_label}.{model_name}: {e}")
        return processed_list

    general_admin_apps = get_model_admin_links(general_models_info)
    ouvidoria_apps = get_model_admin_links(ouvidoria_models_info)
    
    quick_stats = {
        'total_users': User.objects.count(), 
        'total_patds': PATD.objects.count(),
        'active_patds': PATD.objects.exclude(status='finalizado').count(),
        'militares_count': Militar.objects.count(),
    }

    # --- Lógica para Logs do Docker ---
    terminal_logs = []
    try:
        # Tenta conectar ao socket do Docker
        client = docker.from_env()
        containers = client.containers.list()
        
        terminal_logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Conectado ao Daemon do Docker.")
        
        for container in containers:
            # Pega as últimas 5 linhas de log de cada container
            logs = container.logs(tail=5, timestamps=True).decode('utf-8', errors='replace')
            log_entries = logs.split('\n')
            
            for entry in log_entries:
                if entry.strip():
                    # Limita o tamanho da linha para não quebrar o layout CSS
                    clean_entry = entry[:150] + '...' if len(entry) > 150 else entry
                    terminal_logs.append(f"[{container.name}] {clean_entry}")
                    
    except Exception as e:
        # Fallback caso não consiga conectar (ex: desenvolvimento local sem Docker ou socket não montado)
        terminal_logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ERRO: Não foi possível ler logs do Docker.")
        terminal_logs.append(f"Detalhe: {str(e)}")
        terminal_logs.append("Dica: Verifique se '/var/run/docker.sock' está montado no docker-compose.yml")
        
    # Se a lista estiver vazia após a tentativa (sem containers rodando?), adiciona msg padrão
    if not terminal_logs:
         terminal_logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Nenhum container ativo ou logs vazios.")
    # ----------------------------------

    context = {
        'page_title': 'Dashboard da Informática', 
        'general_admin_apps': general_admin_apps,
        'ouvidoria_apps': ouvidoria_apps, 
        'quick_stats': quick_stats,
        'terminal_logs': terminal_logs, # Adicionado ao contexto
    }
    return render(request, 'informatica/dashboard.html', context)

# --- VIEWS CRUD PARA MILITAR ---
class MilitarListView(StaffRequiredMixin, ListView):
    model = Militar
    template_name = 'informatica/militar_list.html'
    context_object_name = 'militares'
    paginate_by = 20
    def get_queryset(self):
        queryset = super().get_queryset().order_by('posto', 'nome_guerra')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(Q(nome_completo__icontains=query) | Q(nome_guerra__icontains=query) | Q(saram__icontains=query) | Q(posto__icontains=query))
        return queryset
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Gerenciar Efetivo"
        context['search_query'] = self.request.GET.get('q', '')
        return context

class MilitarCreateView(StaffRequiredMixin, CreateView):
    model = Militar
    form_class = MilitarForm
    template_name = 'informatica/militar_form.html'
    success_url = reverse_lazy('informatica:militar_list')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Adicionar Militar"
        return context

class MilitarUpdateView(StaffRequiredMixin, UpdateView):
    model = Militar
    form_class = MilitarForm
    template_name = 'informatica/militar_form.html'
    success_url = reverse_lazy('informatica:militar_list')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Editar Militar: {self.object}"
        return context

class MilitarDeleteView(StaffRequiredMixin, DeleteView):
    model = Militar
    template_name = 'informatica/militar_confirm_delete.html'
    success_url = reverse_lazy('informatica:militar_list')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Confirmar Exclusão de {self.object}"
        return context

# --- VIEWS CRUD PARA User ---
class UserListView(StaffRequiredMixin, ListView):
    model = User
    template_name = 'informatica/user_list.html'
    context_object_name = 'users'
    paginate_by = 20
    def get_queryset(self):
        queryset = super().get_queryset().order_by('username')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query) | Q(email__icontains=query))
        return queryset
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Gerenciar Utilizadores"
        context['search_query'] = self.request.GET.get('q', '')
        return context

class UserCreateView(StaffRequiredMixin, CreateView):
    model = User
    form_class = InformaticaUserCreationForm
    template_name = 'informatica/user_form.html'
    success_url = reverse_lazy('informatica:user_list')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Adicionar Utilizador"
        return context

    def form_valid(self, form):
        user = form.save()
        messages.success(self.request, f"Utilizador '{user.username}' criado com senha padrão '12345678'.")
        return redirect(self.success_url)


class UserUpdateView(StaffRequiredMixin, UpdateView):
    model = User
    form_class = InformaticaUserChangeForm
    template_name = 'informatica/user_form.html'
    success_url = reverse_lazy('informatica:user_list')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Editar Utilizador: {self.object.username}"
        return context

class UserDeleteView(StaffRequiredMixin, DeleteView):
    model = User
    template_name = 'informatica/user_confirm_delete.html'
    success_url = reverse_lazy('informatica:user_list')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Confirmar Exclusão de {self.object.username}"
        return context

# --- VIEW PARA RESETAR SENHA ---
@staff_member_required
@require_POST
def reset_user_password(request, pk):
    user_to_reset = get_object_or_404(User, pk=pk)
    try:
        user_to_reset.set_password('12345678')
        user_to_reset.save()
        return JsonResponse({'status': 'success', 'message': f"Senha do utilizador '{user_to_reset.username}' redefinida."})
    except Exception as e:
        logger.error(f"Erro ao redefinir senha para user {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Não foi possível redefinir a senha.'}, status=500)


# --- VIEWS CRUD PARA Group ---
class GroupListView(StaffRequiredMixin, ListView):
    model = Group
    template_name = 'informatica/group_list.html'
    context_object_name = 'groups'
    paginate_by = 20
    def get_queryset(self):
        queryset = super().get_queryset().order_by('name')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(name__icontains=query)
        return queryset
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Gerenciar Grupos de Permissão"
        context['search_query'] = self.request.GET.get('q', '')
        return context

class GroupCreateView(StaffRequiredMixin, CreateView):
    model = Group
    form_class = GroupForm
    template_name = 'informatica/group_form.html'
    success_url = reverse_lazy('informatica:group_list')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Adicionar Grupo de Permissão"
        return context

class GroupUpdateView(StaffRequiredMixin, UpdateView):
    model = Group
    form_class = GroupForm
    template_name = 'informatica/group_form.html'
    success_url = reverse_lazy('informatica:group_list')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Editar Grupo: {self.object.name}"
        return context

class GroupDeleteView(StaffRequiredMixin, DeleteView):
    model = Group
    template_name = 'informatica/group_confirm_delete.html'
    success_url = reverse_lazy('informatica:group_list')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Confirmar Exclusão de {self.object.name}"
        return context

# --- VIEWS CRUD PARA UserProfile ---
class UserProfileListView(StaffRequiredMixin, ListView):
    model = UserProfile
    template_name = 'informatica/userprofile_list.html'
    context_object_name = 'profiles'
    paginate_by = 20
    def get_queryset(self):
        queryset = super().get_queryset().select_related('user', 'militar').order_by('user__username')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(Q(user__username__icontains=query) | Q(militar__nome_guerra__icontains=query))
        return queryset
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Gerenciar Perfis de Utilizador"
        context['search_query'] = self.request.GET.get('q', '')
        return context

class UserProfileUpdateView(StaffRequiredMixin, UpdateView):
    model = UserProfile
    form_class = UserProfileForm
    template_name = 'informatica/userprofile_form.html'
    success_url = reverse_lazy('informatica:userprofile_list')
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Editar Perfil de: {self.object.user.username}"
        return context

# --- VIEW LIST PARA PATD ---
class PATDListView(StaffRequiredMixin, ListView):
    model = PATD
    template_name = 'informatica/patd_list.html'
    context_object_name = 'patds'
    paginate_by = 20
    def get_queryset(self):
        queryset = super().get_queryset().select_related('militar').order_by('-data_inicio')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(Q(numero_patd__icontains=query) | Q(militar__nome_guerra__icontains=query) | Q(militar__nome_completo__icontains=query))
        return queryset
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Visualizar Processos (PATD)"
        context['search_query'] = self.request.GET.get('q', '')
        return context

# --- VIEW UPDATE PARA Configuracao ---
class ConfiguracaoUpdateView(StaffRequiredMixin, UpdateView):
    model = Configuracao
    form_class = ConfiguracaoForm
    template_name = 'informatica/configuracao_form.html'
    success_url = reverse_lazy('informatica:dashboard')

    def get_object(self, queryset=None):
        # Configuracao é um singleton, sempre pega ou cria o objeto com pk=1
        obj, created = Configuracao.objects.get_or_create(pk=1)
        return obj

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Gerenciar Configurações Gerais"
        return context
    
# ... (mantenha os imports existentes)

@staff_member_required
@staff_member_required
def system_logs_api(request):
    logs_data = []
    
    # Lista de termos para ignorar (mantendo a limpeza de logs técnicos)
    ignored_terms = [
        '/static/', 
        '/media/', 
        'GET /api/logs/', # Ignora o próprio polling do terminal
        '/informatica/api/logs/',
        'favicon.ico',
        'POST /jsi18n/', 
        '/admin/jsi18n/',
        'Auto-reloading', 
        'Watching for file changes',
        'http://www.gsd-sys.br/admin/login/?next=/informatica/',
    ]

    try:
        client = docker.from_env()
        containers = client.containers.list()
        
        for container in containers:
            name = container.name.lower()
            
            # --- NOVO FILTRO DE CONTAINERS ---
            # Se o nome do container não contiver 'web', ignoramos.
            # Isso remove automaticamente: nginx, db (postgres), etc.
            if 'web' not in name:
                continue
            # ----------------------------------

            # Pega um buffer maior de logs (100 linhas) para garantir histórico
            log_output = container.logs(tail=100, timestamps=True).decode('utf-8', errors='replace')
            entries = log_output.split('\n')
            
            for entry in entries:
                if not entry.strip():
                    continue
                
                # Aplica os filtros de termos ignorados
                if any(term in entry for term in ignored_terms):
                    continue
                
                # Formatação de timestamp (limpeza visual)
                display_text = entry 
                # Detecta formato padrão Docker/ISO e remove data para economizar espaço
                if len(entry) > 30 and entry[4] == '-' and entry[19] == 'T':
                     display_text = entry[31:] if len(entry) > 31 else entry

                logs_data.append({
                    'container': container.name, 
                    'text': display_text[:300] # Limite de caracteres por linha
                })

    except Exception as e:
        logs_data.append({'container': 'system', 'text': f"Erro leitura logs: {str(e)}"})

    return JsonResponse({'logs': logs_data})
    logs_data = []
    
    # Lista expandida de termos para ignorar nos logs do Docker
    ignored_terms = [
        '/static/',                  # Ignora arquivos CSS/JS/Imagens
        '/media/',                   # Ignora uploads
        '/favicon.ico',              # Ignora ícone do navegador
        '/api/logs/',                # Ignora a própria requisição de log
        'POST /jsi18n/',             # Ignora internacionalização
        '/admin/jsi18n/',
        'Auto-reloading',            # Logs de sistema
        'Watching for file changes',
        'http://www.gsd-sys.br/admin/login/?next=/informatica/', # Ignora redirecionamentos internos de login repetidos
    ]

    try:
        client = docker.from_env()
        containers = client.containers.list()
        
        for container in containers:
            name = container.name.lower()
            
            # Filtra containers: Ignora banco de dados, foca em web e nginx
            if 'db' in name or 'postgres' in name:
                continue
            if not ('web' in name or 'nginx' in name):
                continue

            # Pega os logs
            log_output = container.logs(tail=100, timestamps=True).decode('utf-8', errors='replace')
            entries = log_output.split('\n')
            
            for entry in entries:
                if not entry.strip(): continue
                
                # Se qualquer termo ignorado estiver na linha, pula
                if any(term in entry for term in ignored_terms):
                    continue
                
                # Formatação opcional para logs do Nginx (remove IP e data longa se desejar)
                display_text = entry
                # Tenta limpar o timestamp padrão do Docker para ficar mais curto
                if len(entry) > 30 and entry[4] == '-' and entry[19] == 'T':
                     display_text = entry[31:] if len(entry) > 31 else entry

                logs_data.append({
                    'container': container.name, 
                    'text': display_text[:300] # Limita o comprimento da linha
                })

    except Exception as e:
        logs_data.append({'container': 'system', 'text': f"Erro leitura logs: {str(e)}"})

    return JsonResponse({'logs': logs_data})