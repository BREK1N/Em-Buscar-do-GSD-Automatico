# GsdAutomatico/informatica/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.apps import apps
from django.urls import reverse, NoReverseMatch, reverse_lazy
from django.contrib.auth.models import User, Group
from Ouvidoria.models import PATD, Anexo, Configuracao
from Secao_pessoal.models import Efetivo, Setor # ATUALIZADO
from login.models import UserProfile
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .forms import (
    InformaticaUserCreationForm, InformaticaUserChangeForm,
    GroupForm, ConfiguracaoForm
)
from .models import GrupoMaterial, SubgrupoMaterial, Material, Cautela, CautelaItem, Armario, Prateleira, GroupProfile, SECAO_CHOICES
from django.db.models import Q, ProtectedError
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
import json
import datetime
import docker
import requests
import os
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth import authenticate # Importação para validar senha

logger = logging.getLogger(__name__)

def is_staff(user):
    return user.is_staff

class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = reverse_lazy('login:login')
    def test_func(self): return is_staff(self.request.user)
    def handle_no_permission(self): return super().handle_no_permission()

# ==========================================
# VIEWS DE DASHBOARD E CRUD BÁSICO
# ==========================================
@staff_member_required
def dashboard(request):
    general_models_info = [
        ('auth', 'user', 'Utilizadores', 'Utilizador'),
        ('auth', 'group', 'Grupos de Permissão', 'Grupo'),
    ]
    ouvidoria_models_info = [
        ('Secao_pessoal', 'efetivo', 'Efetivo (Militares)', 'Militar'),
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
                    except NoReverseMatch: pass
                else:
                    try: item_data['list_url'] = reverse(list_url_name)
                    except NoReverseMatch: pass
                    try: item_data['add_url'] = reverse(add_url_name)
                    except NoReverseMatch: pass
                    item_data['count'] = model.objects.count()

                processed_list.append(item_data)
            except Exception as e: logger.error(f"Erro: {e}")
        return processed_list

    general_admin_apps = get_model_admin_links(general_models_info)
    ouvidoria_apps = get_model_admin_links(ouvidoria_models_info)
    
    quick_stats = {
        'total_users': User.objects.count(), 
        'total_patds': PATD.objects.count(),
        'active_patds': PATD.objects.exclude(status='finalizado').count(),
        'militares_count': Efetivo.objects.count(),
    }

    terminal_logs = []
    try:
        client = docker.from_env()
        containers = client.containers.list()
        terminal_logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Conectado ao Daemon do Docker.")
        for container in containers:
            logs = container.logs(tail=5, timestamps=True).decode('utf-8', errors='replace')
            for entry in logs.split('\n'):
                if entry.strip():
                    clean_entry = entry[:150] + '...' if len(entry) > 150 else entry
                    terminal_logs.append(f"[{container.name}] {clean_entry}")
    except Exception as e:
        terminal_logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] ERRO: Não foi possível ler logs do Docker.")
        terminal_logs.append(f"Detalhe: {str(e)}")
        
    if not terminal_logs:
         terminal_logs.append(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Nenhum container ativo ou logs vazios.")

    context = {
        'page_title': 'Dashboard da Informática', 
        'general_admin_apps': general_admin_apps,
        'ouvidoria_apps': ouvidoria_apps, 
        'quick_stats': quick_stats,
        'terminal_logs': terminal_logs,
    }
    return render(request, 'informatica/dashboard.html', context)


class UserListView(StaffRequiredMixin, ListView):
    model = User
    template_name = 'informatica/user_list.html'
    context_object_name = 'users'
    paginate_by = 20
    def get_queryset(self):
        queryset = super().get_queryset().select_related('profile__militar').order_by('username')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(
                Q(username__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query) |
                Q(email__icontains=query) |
                Q(profile__militar__nome_guerra__icontains=query)
            ).distinct()
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

@staff_member_required
@require_POST
def reset_user_password(request, pk):
    user_to_reset = get_object_or_404(User, pk=pk)
    try:
        user_to_reset.set_password('12345678')
        user_to_reset.save()
        return JsonResponse({'status': 'success', 'message': f"Senha do utilizador '{user_to_reset.username}' redefinida."})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': 'Não foi possível redefinir a senha.'}, status=500)

class GroupListView(StaffRequiredMixin, ListView):
    model = Group
    template_name = 'informatica/group_list.html'
    context_object_name = 'groups'
    paginate_by = 9999  # agrupamos manualmente, sem paginação por página
    def get_queryset(self):
        queryset = super().get_queryset().select_related('secao_profile').order_by('name')
        query = self.request.GET.get('q')
        if query:
            queryset = queryset.filter(name__icontains=query)
        return queryset
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Gerenciar Grupos"
        context['search_query'] = self.request.GET.get('q', '')
        context['secao_ativa'] = self.request.GET.get('secao', 'todas')
        context['secao_choices'] = SECAO_CHOICES
        # Agrupa grupos por seção
        from collections import defaultdict
        grupos_por_secao = defaultdict(list)
        for g in context['groups']:
            secao = getattr(g.secao_profile, 'secao', 'geral') if hasattr(g, 'secao_profile') else 'geral'
            grupos_por_secao[secao].append(g)
        # Garante que todas as seções com grupos apareçam, na ordem de SECAO_CHOICES
        secao_labels = dict(SECAO_CHOICES)
        context['grupos_por_secao'] = [
            {'key': key, 'label': label, 'groups': grupos_por_secao.get(key, [])}
            for key, label in SECAO_CHOICES
            if grupos_por_secao.get(key)
        ]
        return context

def _get_perms_por_app():
    from django.contrib.auth.models import Permission
    from collections import defaultdict
    agrupado = defaultdict(lambda: {'label': '', 'perms': []})
    for perm in Permission.objects.select_related('content_type').order_by(
            'content_type__app_label', 'content_type__model', 'codename'):
        app = perm.content_type.app_label
        agrupado[app]['label'] = app.replace('_', ' ').title()
        agrupado[app]['perms'].append({'id': perm.pk, 'name': perm.name, 'codename': perm.codename})
    return dict(agrupado)

class GroupCreateView(StaffRequiredMixin, CreateView):
    model = Group
    form_class = GroupForm
    template_name = 'informatica/group_form.html'
    success_url = reverse_lazy('informatica:group_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        secao = self.request.POST.get('secao', 'geral')
        GroupProfile.objects.update_or_create(group=self.object, defaults={'secao': secao})
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = "Novo Grupo"
        context['perms_por_app'] = _get_perms_por_app()
        context['selected_perm_ids'] = []
        context['secao_choices'] = SECAO_CHOICES
        context['secao_atual'] = 'geral'
        return context

class GroupUpdateView(StaffRequiredMixin, UpdateView):
    model = Group
    form_class = GroupForm
    template_name = 'informatica/group_form.html'
    success_url = reverse_lazy('informatica:group_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        secao = self.request.POST.get('secao', 'geral')
        GroupProfile.objects.update_or_create(group=self.object, defaults={'secao': secao})
        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = f"Editar Grupo: {self.object.name}"
        context['perms_por_app'] = _get_perms_por_app()
        context['selected_perm_ids'] = list(self.object.permissions.values_list('id', flat=True))
        context['secao_choices'] = SECAO_CHOICES
        profile = GroupProfile.objects.filter(group=self.object).first()
        context['secao_atual'] = profile.secao if profile else 'geral'
        return context

class GroupDeleteView(StaffRequiredMixin, DeleteView):
    model = Group
    template_name = 'informatica/group_confirm_delete.html'
    success_url = reverse_lazy('informatica:group_list')

    def form_valid(self, form):
        GroupProfile.objects.filter(group=self.object).delete()
        return super().form_valid(form)


class ConfiguracaoUpdateView(StaffRequiredMixin, UpdateView):
    model = Configuracao
    form_class = ConfiguracaoForm
    template_name = 'informatica/configuracao_form.html'
    success_url = reverse_lazy('informatica:dashboard')
    def get_object(self, queryset=None):
        obj, created = Configuracao.objects.get_or_create(pk=1)
        return obj


# ==========================================
# LOGS E MONITORAMENTO
# ==========================================
@staff_member_required
def system_logs_api(request):
    logs_data = []
    ignored_terms = ['/static/', '/media/', '/favicon.ico', '/api/logs/', 'POST /jsi18n/', 'Auto-reloading', 'Watching for file changes', '/admin/login/']
    try:
        client = docker.from_env()
        containers = client.containers.list()
        for container in containers:
            name = container.name.lower()
            if 'db' in name or 'postgres' in name: continue
            if not ('web' in name or 'nginx' in name): continue
            log_output = container.logs(tail=100, timestamps=True).decode('utf-8', errors='replace')
            for entry in log_output.split('\n'):
                if not entry.strip(): continue
                if any(term in entry for term in ignored_terms): continue
                display_text = entry[31:] if len(entry) > 31 and entry[4] == '-' and entry[19] == 'T' else entry
                logs_data.append({'container': container.name, 'text': display_text[:300]})
    except Exception as e:
        logs_data.append({'container': 'system', 'text': f"Erro: {str(e)}"})
    return JsonResponse({'logs': logs_data})

URL_MONITOR = "http://10.52.18.29:5000"
LOG_FILE_PATH = "/logs_do_host/backup_sender.log"

@login_required
def monitoramento_backup(request):
    if not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    context = {}
    try:
        response = requests.get(URL_MONITOR, timeout=5)
        if response.status_code == 200:
            dados = response.json()
            context['online'] = True
            context['dados'] = dados
        else:
            context['online'] = False
            context['erro'] = f"Erro HTTP: {response.status_code}"
    except Exception as e:
        context['online'] = False
        context['erro'] = str(e)
    return render(request, 'informatica/monitoramento.html', context)

@login_required
def visualizar_logs_backup(request):
    if not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    logs = []
    try:
        if os.path.exists(LOG_FILE_PATH):
            with open(LOG_FILE_PATH, 'r') as f: logs = f.readlines()[-100:]
        else: logs = [f"Arquivo não encontrado: {LOG_FILE_PATH}"]
    except Exception as e: logs = [str(e)]
    return render(request, 'informatica/logs_backup.html', {'logs': logs})


# ==========================================
# MÓDULO GESTÃO DE MATERIAIS E CAUTELAS
# ==========================================
@staff_member_required
def gestao_materiais_view(request):
    militares = Efetivo.objects.all().order_by('posto', 'nome_guerra')
    
    militares_info = Efetivo.objects.filter(
        Q(setor__icontains='informática') | Q(subsetor__icontains='informática') |
        Q(setor__icontains='informatica') | Q(subsetor__icontains='informatica')
    ).order_by('posto', 'nome_guerra')

    grupos = GrupoMaterial.objects.all().order_by('nome')
    subgrupos = SubgrupoMaterial.objects.all().select_related('grupo').order_by('grupo__nome', 'nome')
    
    # 1. Busque os setores
    setores = Setor.objects.all().order_by('nome')

    # 2. Atualize a query de materiais para incluir 'secao' no select_related
    materiais = Material.objects.all().select_related('subgrupo__grupo', 'prateleira__armario', 'secao').order_by('nome')
    
    # Busca armários para o painel de armários e selects
    armarios = Armario.objects.all().prefetch_related('prateleiras__materiais').order_by('nome')
    
    cautelas_ativas = Cautela.objects.filter(ativa=True).select_related('sobreaviso', 'recebedor').order_by('-data_emissao')
    cautelas_historico = Cautela.objects.filter(ativa=False).select_related('sobreaviso', 'recebedor').order_by('-data_emissao')

    materiais_disponiveis = materiais.filter(quantidade_disponivel__gt=0, funcionando=True)
    
    materiais_json = [{
        'id': mat.id, 'grupo_id': mat.subgrupo.grupo.id, 'grupo_nome': mat.subgrupo.grupo.nome,
        'nome': mat.nome, 'serial': mat.serial or '', 'quantidade_disponivel': mat.quantidade_disponivel,
        'atributos': mat.atributos_extras or {}
    } for mat in materiais_disponiveis]
    
    acervo_json = [{
        'id': mat.id, 
        'subgrupo_id': mat.subgrupo.id, 
        'subgrupo_nome': mat.subgrupo.nome,
        'grupo_id': mat.subgrupo.grupo.id,
        'grupo_nome': mat.subgrupo.grupo.nome,
        'nome': mat.nome,
        'codigo': mat.codigo or '', 'serial': mat.serial or '',
        'quantidade': mat.quantidade, 'quantidade_disponivel': mat.quantidade_disponivel,
        'funcionando': 1 if mat.funcionando else 0,
        'motivo_defeito': mat.motivo_defeito or '',
        'atributos': mat.atributos_extras or {},
        'prateleira_id': mat.prateleira.id if mat.prateleira else None,
        'prateleira_nome': mat.prateleira.nome if mat.prateleira else None,
        'armario_id': mat.prateleira.armario.id if mat.prateleira else None,
        'armario_nome': mat.prateleira.armario.nome if mat.prateleira else None,
        'secao_id': mat.secao.id if mat.secao else '',
        'secao_nome': mat.secao.nome if mat.secao else 'Geral/Estoque',
    } for mat in materiais]

    militares_dados_json = []
    for m in militares:
        last_cautela = Cautela.objects.filter(recebedor=m).order_by('-data_emissao').first()
        telefone = last_cautela.telefone_contato if last_cautela and last_cautela.telefone_contato else ''
        militares_dados_json.append({'id': m.id, 'telefone': telefone, 'saram': getattr(m, 'saram', '')})

    militares_info_json = []
    for m in militares_info:
        militares_info_json.append({
            'id': m.id,
            'assinatura': getattr(m, 'assinatura', None)
        })
        
    armarios_json = [{
        'id': arm.id, 'nome': arm.nome, 'localizacao': arm.localizacao or '',
        'prateleiras': [{'id': p.id, 'nome': p.nome} for p in arm.prateleiras.all()]
    } for arm in armarios]

    # 4. Adicione os setores ao contexto
    context = {
        'page_title': 'Gestão de Materiais e Cautelas',
        'militares': militares,
        'militares_info': militares_info,
        'grupos': grupos, 'subgrupos': subgrupos, 'materiais': materiais,
        'armarios': armarios,
        'setores': setores,
        'cautelas_ativas': cautelas_ativas, 'cautelas_historico': cautelas_historico,
        'materiais_json': json.dumps(materiais_json),
        'acervo_json': json.dumps(acervo_json),
        'militares_dados_json': json.dumps(militares_dados_json),
        'militares_info_json': json.dumps(militares_info_json),
        'armarios_json': json.dumps(armarios_json),
    }
    return render(request, 'informatica/gestao_materiais.html', context)


@staff_member_required
@require_POST
def api_add_grupo(request):
    data = json.loads(request.body)
    try:
        GrupoMaterial.objects.create(nome=data.get('nome'))
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
@require_POST
def api_add_subgrupo(request):
    data = json.loads(request.body)
    try:
        grupo = GrupoMaterial.objects.get(id=data.get('grupo_id'))
        SubgrupoMaterial.objects.create(grupo=grupo, nome=data.get('nome'))
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
@require_POST
def api_add_armario(request):
    data = json.loads(request.body)
    try:
        Armario.objects.create(nome=data.get('nome'), localizacao=data.get('localizacao', ''))
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
@require_POST
def api_add_prateleira(request):
    data = json.loads(request.body)
    try:
        armario = Armario.objects.get(id=data.get('armario_id'))
        Prateleira.objects.create(armario=armario, nome=data.get('nome'))
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
@require_POST
def api_edit_armario(request, pk):
    data = json.loads(request.body)
    try:
        armario = Armario.objects.get(pk=pk)
        armario.nome = data.get('nome')
        armario.localizacao = data.get('localizacao', '')
        armario.save()
        return JsonResponse({'status': 'success'})
    except Exception as e: 
        return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
@require_POST
def api_delete_armario(request, pk):
    try:
        armario = Armario.objects.get(pk=pk)
        armario.delete() # Excluirá prateleiras (CASCADE). Materiais ficarão com local = NULL (SET_NULL)
        return JsonResponse({'status': 'success'})
    except Exception as e: 
        return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
@require_POST
def api_edit_prateleira(request, pk):
    data = json.loads(request.body)
    try:
        prateleira = Prateleira.objects.get(pk=pk)
        prateleira.nome = data.get('nome')
        prateleira.save()
        return JsonResponse({'status': 'success'})
    except Exception as e: 
        return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
@require_POST
def api_delete_prateleira(request, pk):
    try:
        prateleira = Prateleira.objects.get(pk=pk)
        prateleira.delete()
        return JsonResponse({'status': 'success'})
    except Exception as e: 
        return JsonResponse({'status': 'error', 'message': str(e)})


@staff_member_required
@require_POST
def api_add_material(request):
    data = json.loads(request.body)
    try:
        subgrupo = SubgrupoMaterial.objects.get(id=data.get('subgrupo_id'))
        prateleira_id = data.get('prateleira_id')
        prateleira = Prateleira.objects.get(id=prateleira_id) if prateleira_id else None
        
        secao_id = data.get('secao_id')
        secao = Setor.objects.get(id=secao_id) if secao_id else None
        
        serial = data.get('serial')
        qtd = int(data.get('quantidade', 1))
        
        if serial and Material.objects.filter(subgrupo__grupo=subgrupo.grupo, serial=serial).exists():
            return JsonResponse({'status': 'error', 'message': f"O serial '{serial}' já está em uso nesta categoria."})

        Material.objects.create(
            subgrupo=subgrupo,
            secao=secao,
            nome=data.get('nome'),
            codigo=data.get('codigo'),
            serial=serial,
            prateleira=prateleira,
            quantidade=qtd,
            quantidade_disponivel=qtd,
            funcionando=data.get('funcionando', True),
            motivo_defeito=data.get('motivo_defeito', ''),
            atributos_extras=data.get('atributos_extras', {})
        )
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
@require_POST
def api_edit_material(request, pk):
    data = json.loads(request.body)
    try:
        material = Material.objects.get(pk=pk)
        subgrupo = SubgrupoMaterial.objects.get(id=data.get('subgrupo_id'))
        prateleira_id = data.get('prateleira_id')
        prateleira = Prateleira.objects.get(id=prateleira_id) if prateleira_id else None
        
        secao_id = data.get('secao_id')
        secao = Setor.objects.get(id=secao_id) if secao_id else None
        
        serial = data.get('serial')
        qtd = int(data.get('quantidade', 1))
        
        if serial and serial != material.serial and Material.objects.filter(subgrupo__grupo=subgrupo.grupo, serial=serial).exists():
            return JsonResponse({'status': 'error', 'message': f"O serial '{serial}' já está em uso nesta categoria."})

        diff = qtd - material.quantidade
        nova_disp = material.quantidade_disponivel + diff
        
        if nova_disp < 0:
            return JsonResponse({'status': 'error', 'message': 'A quantidade total não pode ser menor que a quantidade que já está emprestada!'})
            
        material.subgrupo = subgrupo
        material.secao = secao
        material.nome = data.get('nome')
        material.codigo = data.get('codigo')
        material.serial = serial
        material.prateleira = prateleira
        material.quantidade = qtd
        material.quantidade_disponivel = nova_disp
        material.funcionando = data.get('funcionando', True)
        material.motivo_defeito = data.get('motivo_defeito', '')
        material.atributos_extras = data.get('atributos_extras', {})
        
        if material.quantidade_disponivel == 0:
            material.disponivel = False
        else:
            material.disponivel = True
            
        material.save()
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
@require_POST
def api_delete_material(request, pk):
    data = json.loads(request.body)
    password = data.get('password')
    
    # Autenticação dupla para excluir materiais
    user = authenticate(username=request.user.username, password=password)
    if user is None:
        return JsonResponse({'status': 'error', 'message': 'Senha incorreta. A exclusão não foi autorizada.'})
        
    try:
        material = Material.objects.get(pk=pk)
        material.delete()
        return JsonResponse({'status': 'success'})
    except ProtectedError:
        return JsonResponse({'status': 'error', 'message': 'Este material não pode ser excluído pois faz parte do histórico de uma ou mais cautelas. Sugestão: Marque-o como "Com Defeito" ou Inoperante.'})
    except Exception as e: 
        return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
@require_POST
def api_delete_grupo(request, pk):
    try:
        grupo = GrupoMaterial.objects.get(pk=pk)
        if Material.objects.filter(subgrupo__grupo=grupo).exists():
            return JsonResponse({'status': 'error', 'message': 'Existem materiais cadastrados neste grupo.'})
        grupo.delete()
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
@require_POST
def api_delete_subgrupo(request, pk):
    try:
        subgrupo = SubgrupoMaterial.objects.get(pk=pk)
        if subgrupo.materiais.exists():
            return JsonResponse({'status': 'error', 'message': 'Existem materiais cadastrados neste subgrupo.'})
        subgrupo.delete()
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})


@staff_member_required
@require_POST
def api_salvar_cautela(request):
    data = json.loads(request.body)
    try:
        sobreaviso = Efetivo.objects.get(id=data.get('sobreaviso_id'))
        recebedor = Efetivo.objects.get(id=data.get('recebedor_id'))
        materiais_list = data.get('materiais', [])
        
        if not materiais_list: return JsonResponse({'status': 'error', 'message': 'Nenhum material selecionado.'})

        if data.get('salvar_padrao') and data.get('assinatura_sobreaviso'):
            sobreaviso.assinatura = data.get('assinatura_sobreaviso')
            sobreaviso.save()

        cautela = Cautela.objects.create(
            sobreaviso=sobreaviso,
            recebedor=recebedor,
            assinatura_sobreaviso=data.get('assinatura_sobreaviso'),
            assinatura_recebedor=data.get('assinatura_recebedor'),
            nome_missao=data.get('nome_missao', ''),
            telefone_contato=data.get('telefone_contato', '')
        )
        
        for mat_data in materiais_list:
            material = Material.objects.get(id=mat_data['id'])
            qtd = int(mat_data['qtd'])
            if material.quantidade_disponivel < qtd:
                raise ValueError(f"Material {material.nome} só tem {material.quantidade_disponivel} disponíveis!")
                
            CautelaItem.objects.create(cautela=cautela, material=material, quantidade=qtd)
            material.quantidade_disponivel -= qtd
            if material.quantidade_disponivel == 0: material.disponivel = False
            material.save()
            
        return JsonResponse({'status': 'success', 'cautela_id': cautela.id})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
@require_POST
def api_devolver_cautela(request, pk):
    data = json.loads(request.body)
    try:
        cautela = Cautela.objects.get(id=pk)
        sobreaviso_devolucao = Efetivo.objects.get(id=data.get('sobreaviso_id'))
        
        cautela.ativa = False
        cautela.data_devolucao = timezone.now()
        cautela.recebedor_devolucao = sobreaviso_devolucao
        cautela.assinatura_devolucao = data.get('assinatura_devolucao')
        cautela.save()
        
        for item in cautela.itens.filter(devolvido=False):
            item.devolvido = True
            item.data_devolucao = timezone.now()
            item.recebedor_devolucao = sobreaviso_devolucao
            item.assinatura_devolucao = data.get('assinatura_devolucao')
            item.save()
            item.material.quantidade_disponivel += item.quantidade
            item.material.disponivel = True
            item.material.save()
            
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
@require_POST
def api_devolver_item_cautela(request, item_id):
    data = json.loads(request.body)
    try:
        item = CautelaItem.objects.get(id=item_id)
        sobreaviso_devolucao = Efetivo.objects.get(id=data.get('sobreaviso_id'))
        
        item.devolvido = True
        item.data_devolucao = timezone.now()
        item.recebedor_devolucao = sobreaviso_devolucao
        item.assinatura_devolucao = data.get('assinatura_devolucao')
        item.save()
        
        item.material.quantidade_disponivel += item.quantidade
        item.material.disponivel = True
        item.material.save()
        
        cautela = item.cautela
        if not cautela.itens.filter(devolvido=False).exists():
            cautela.ativa = False
            cautela.data_devolucao = timezone.now()
            cautela.recebedor_devolucao = sobreaviso_devolucao
            cautela.assinatura_devolucao = data.get('assinatura_devolucao')
            cautela.save()
            
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

@staff_member_required
@require_POST
def api_devolver_multiplos_itens(request, cautela_id):
    data = json.loads(request.body)
    try:
        cautela = Cautela.objects.get(id=cautela_id)
        sobreaviso_devolucao = Efetivo.objects.get(id=data.get('sobreaviso_id'))
        item_ids = data.get('item_ids', [])
        
        for item_id in item_ids:
            item = CautelaItem.objects.get(id=item_id, cautela=cautela)
            if not item.devolvido:
                item.devolvido = True
                item.data_devolucao = timezone.now()
                item.recebedor_devolucao = sobreaviso_devolucao
                item.assinatura_devolucao = data.get('assinatura_devolucao')
                item.save()
                
                item.material.quantidade_disponivel += item.quantidade
                item.material.disponivel = True
                item.material.save()
        
        # Se depois dessa baixa múltipla todos os itens estiverem devolvidos, baixa a cautela inteira
        if not cautela.itens.filter(devolvido=False).exists():
            cautela.ativa = False
            cautela.data_devolucao = timezone.now()
            cautela.recebedor_devolucao = sobreaviso_devolucao
            cautela.assinatura_devolucao = data.get('assinatura_devolucao')
            cautela.save()
            
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})


@staff_member_required
@require_POST
def api_add_item_cautela(request, cautela_id):
    data = json.loads(request.body)
    try:
        cautela = Cautela.objects.get(id=cautela_id)
        material = Material.objects.get(id=data.get('material_id'))
        qtd = int(data.get('quantidade', 1))
        
        if material.quantidade_disponivel < qtd:
            return JsonResponse({'status': 'error', 'message': f'Estoque insuficiente. Apenas {material.quantidade_disponivel} disponíveis.'})
            
        CautelaItem.objects.create(cautela=cautela, material=material, quantidade=qtd)
        
        material.quantidade_disponivel -= qtd
        if material.quantidade_disponivel == 0:
            material.disponivel = False
        material.save()
        
        return JsonResponse({'status': 'success'})
    except Exception as e: return JsonResponse({'status': 'error', 'message': str(e)})

from django.http import HttpResponse

@staff_member_required
def exportar_armarios_excel(request):
    try:
        import openpyxl
        from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        return HttpResponse("Erro: A biblioteca 'openpyxl' não está instalada. Execute 'pip install openpyxl' no ambiente do servidor.", status=500)

    armarios_ids = request.GET.get('armarios', '')
    is_completo = request.GET.get('completo') == 'true'

    query = Armario.objects.all().prefetch_related('prateleiras__materiais')
    
    if armarios_ids:
        ids = [int(i) for i in armarios_ids.split(',') if i.isdigit()]
        if ids:
            query = query.filter(id__in=ids)
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Inventário de Armários"
    
    # Estilos de Formatação
    header_font = Font(bold=True, color="FFFFFF", size=12)
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    title_font = Font(bold=True, size=16, color="1F4E78")
    
    align_center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    align_left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'), bottom=Side(style='thin'))
    
    # Título do Relatório (Linha 1)
    max_col = 10 if is_completo else 8
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max_col)
    title_cell = ws.cell(row=1, column=1, value=f"Relatório de Inventário de Armários - {'Completo' if is_completo else 'Simplificado'} ({timezone.now().strftime('%d/%m/%Y')})")
    title_cell.font = title_font
    title_cell.alignment = align_center
    ws.row_dimensions[1].height = 30
    
    # Cabeçalhos (Linha 2)
    if is_completo:
        headers = ['Armário', 'Localização', 'Prateleira', 'Material', 'S/N', 'Código Interno', 'Qtd', 'Status', 'Atributos Técnicos', 'Observações/Defeito']
    else:
        headers = ['Armário', 'Localização', 'Prateleira', 'Material', 'S/N', 'Código Interno', 'Qtd', 'Status']
        
    ws.append(headers)
    
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col_num)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = align_center
        cell.border = thin_border
        
    current_row = 3
    for armario in query:
        prateleiras = armario.prateleiras.all()
        if not prateleiras:
            row_data = [armario.nome, armario.localizacao or '-', 'Sem Prateleiras', '-', '-', '-', '-', '-']
            if is_completo: row_data.extend(['-', '-'])
            ws.append(row_data)
            for col_num in range(1, len(row_data) + 1):
                ws.cell(row=current_row, column=col_num).border = thin_border
                ws.cell(row=current_row, column=col_num).alignment = align_center
            current_row += 1
            continue
            
        for prateleira in prateleiras:
            materiais = prateleira.materiais.all()
            if not materiais:
                row_data = [armario.nome, armario.localizacao or '-', prateleira.nome, 'Vazia', '-', '-', '-', '-']
                if is_completo: row_data.extend(['-', '-'])
                ws.append(row_data)
                for col_num in range(1, len(row_data) + 1):
                    ws.cell(row=current_row, column=col_num).border = thin_border
                    ws.cell(row=current_row, column=col_num).alignment = align_center
                current_row += 1
                continue
                
            for mat in materiais:
                status = 'Funcionando' if mat.funcionando else 'Com Defeito'
                row_data = [
                    armario.nome,
                    armario.localizacao or '-',
                    prateleira.nome,
                    mat.nome,
                    mat.serial or '-',
                    mat.codigo or '-',
                    mat.quantidade,
                    status
                ]
                
                if is_completo:
                    attrs_str = "-"
                    if mat.atributos_extras:
                        # Junta os atributos com quebras de linha
                        attrs_str = "\n".join([f"• {k}: {v}" for k, v in mat.atributos_extras.items()])
                    row_data.append(attrs_str)
                    row_data.append(mat.motivo_defeito or '-')
                    
                ws.append(row_data)
                
                # Aplica estilos nas células inseridas
                for col_num, val in enumerate(row_data, 1):
                    cell = ws.cell(row=current_row, column=col_num)
                    cell.border = thin_border
                    # Alinha à esquerda apenas colunas de texto descritivo
                    if col_num in [4, 9, 10]:
                        cell.alignment = align_left
                    else:
                        cell.alignment = align_center
                
                current_row += 1
                
    # Auto-ajuste de largura das colunas
    for col_idx, col in enumerate(ws.columns, 1):
        max_length = 0
        column = get_column_letter(col_idx)
        for cell in col:
            try:
                # Ignora a linha do título principal na contagem de largura
                if cell.row > 1: 
                    lines = str(cell.value).split('\n')
                    for line in lines:
                        if len(line) > max_length:
                            max_length = len(line)
            except:
                pass
        
        # Define largura máxima de 45 para não criar colunas absurdamente gigantes
        adjusted_width = min(max_length + 2, 45) 
        ws.column_dimensions[column].width = adjusted_width

    # Adiciona Filtros (Setinhas) na tabela (A2:J[ultima_linha])
    ws.auto_filter.ref = f"A2:{get_column_letter(max_col)}{current_row - 1}"

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    filename = "Inventario_Completo.xlsx" if is_completo else "Inventario_Simplificado.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response

@staff_member_required
def imprimir_cautela(request, pk):
    cautela = get_object_or_404(Cautela, id=pk)
    return render(request, 'informatica/cautela_print.html', {'cautela': cautela})