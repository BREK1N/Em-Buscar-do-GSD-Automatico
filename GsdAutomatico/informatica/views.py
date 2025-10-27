# GsdAutomatico/informatica/views.py

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.apps import apps
from django.urls import reverse, NoReverseMatch, reverse_lazy # Adicionar reverse_lazy
from django.contrib.auth.models import User, Group
from Ouvidoria.models import Militar, PATD, Anexo, Configuracao # Modelos da Ouvidoria
from login.models import UserProfile # Modelo do Login
from django.views.generic import ListView, CreateView, UpdateView, DeleteView # Importar CBVs
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin # Importar Mixins
from .forms import MilitarForm # Importar o form criado
from django.db.models import Q # Para pesquisa
import logging # Importar logging

logger = logging.getLogger(__name__) # Configurar logger

# Função helper para verificar se é staff
def is_staff(user):
    return user.is_staff

class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    """ Mixin para garantir que o utilizador é staff """
    login_url = reverse_lazy('login:login') # Redireciona para o login se não estiver logado
    def test_func(self):
        return is_staff(self.request.user)

    def handle_no_permission(self):
        # Pode adicionar uma mensagem de erro se quiser
        # from django.contrib import messages
        # messages.error(self.request, "Acesso negado. Apenas administradores.")
        return super().handle_no_permission()


# --- View do Dashboard ---
@staff_member_required
def dashboard(request):
    # Modelos Gerais (App Label, Model Name, Plural Display Name, Singular Display Name)
    general_models_info = [
        ('auth', 'user', 'Utilizadores', 'Utilizador'),
        ('auth', 'group', 'Grupos de Permissão', 'Grupo'),
        ('login', 'userprofile', 'Perfis de Utilizador', 'Perfil'),
    ]

    # Modelos da Ouvidoria
    ouvidoria_models_info = [
        ('Ouvidoria', 'militar', 'Efetivo (Militares)', 'Militar'),
        ('Ouvidoria', 'patd', 'Processos (PATD)', 'PATD'),
        # Ajuste para Configuração
        ('Ouvidoria', 'configuracao', 'Configurações Gerais', 'Configuração'),
    ]

    def get_model_admin_links(model_info_list):
        processed_list = []
        for app_label, model_name, plural_name, singular_name in model_info_list:
            item_data = {
                'name': plural_name,
                'singular': singular_name,
                'model_name': model_name,
                'list_url': '#',
                'add_url': '#',
                'edit_config_url': '#', # Adicionado para flexibilidade
                'count': None
            }
            try:
                model = apps.get_model(app_label, model_name)
                list_url_name = f'informatica:{model_name}_list'
                add_url_name = f'informatica:{model_name}_add'
                edit_config_url_name = f'informatica:manage_config' # URL específica para config

                if model_name == 'configuracao':
                    try:
                        # O link principal (e único) para config vai para a edição
                        item_data['edit_config_url'] = reverse(edit_config_url_name)
                        item_data['list_url'] = item_data['edit_config_url'] # Faz 'Ver Lista' ir para editar
                        item_data['add_url'] = item_data['edit_config_url']  # Faz 'Adicionar' ir para editar (ou ocultar no template)
                    except NoReverseMatch:
                        logger.warning(f"URL '{edit_config_url_name}' ainda não definida.")
                else:
                    try:
                        item_data['list_url'] = reverse(list_url_name)
                    except NoReverseMatch:
                        logger.warning(f"URL '{list_url_name}' ainda não definida.")
                    try:
                        item_data['add_url'] = reverse(add_url_name)
                    except NoReverseMatch:
                        logger.warning(f"URL '{add_url_name}' ainda não definida.")
                    # Conta objetos apenas para modelos que não são singleton
                    item_data['count'] = model.objects.count()

                processed_list.append(item_data)

            except LookupError:
                logger.warning(f"Modelo {app_label}.{model_name} não encontrado.")
            except Exception as e:
                logger.error(f"Erro ao processar modelo {app_label}.{model_name}: {e}")
        return processed_list

    general_admin_apps = get_model_admin_links(general_models_info)
    ouvidoria_apps = get_model_admin_links(ouvidoria_models_info)

    quick_stats = {
        'total_users': User.objects.count(),
        'total_patds': PATD.objects.count(),
        'active_patds': PATD.objects.exclude(status='finalizado').count(),
        'militares_count': Militar.objects.count(),
    }

    context = {
        'page_title': 'Dashboard da Informática',
        'general_admin_apps': general_admin_apps,
        'ouvidoria_apps': ouvidoria_apps,
        'quick_stats': quick_stats,
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
            queryset = queryset.filter(
                Q(nome_completo__icontains=query) |
                Q(nome_guerra__icontains=query) |
                Q(saram__icontains=query) |
                Q(posto__icontains=query)
            )
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

# --- Adicione aqui as views para User, Group, PATD (apenas lista), Configuracao, etc. ---
# Exemplo (ainda precisa criar o template informatica/patd_list.html):
class PATDListView(StaffRequiredMixin, ListView):
    model = PATD
    template_name = 'informatica/patd_list.html' # Criar este template
    context_object_name = 'patds'
    paginate_by = 20

    def get_queryset(self):
        # Listar todas as PATDs, talvez ordenadas pela mais recente
        queryset = super().get_queryset().select_related('militar').order_by('-data_inicio')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(numero_patd__icontains=query) |
                Q(militar__nome_guerra__icontains=query) |
                Q(militar__nome_completo__icontains=query)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Visualizar Processos (PATD)"
        context['search_query'] = self.request.GET.get('q', '')
        return context

# --- View para gerenciar Configurações ---
# (Precisa criar informatica/forms.py com ConfiguracaoForm e o template)
# class ConfiguracaoUpdateView(StaffRequiredMixin, UpdateView):
#     model = Configuracao
#     form_class = ConfiguracaoForm # Criar este form
#     template_name = 'informatica/configuracao_form.html' # Criar este template
#     success_url = reverse_lazy('informatica:dashboard') # Volta para o dashboard
#
#     def get_object(self, queryset=None):
#         # Configuracao é um singleton, sempre pega o objeto com pk=1
#         obj, created = Configuracao.objects.get_or_create(pk=1)
#         return obj
#
#     def get_context_data(self, **kwargs):
#         context = super().get_context_data(**kwargs)
#         context['page_title'] = "Gerenciar Configurações Gerais"
#         return context