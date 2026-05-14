import json
from datetime import datetime, date, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.http import JsonResponse
from django.db.models import Q, Case, When, Value, IntegerField
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model

from Secao_pessoal.models import Efetivo
from .models import RegistroChamada


@login_required
def chamada_index(request):
    militar_logado = getattr(request.user, 'profile', None) and request.user.profile.militar
    
    if not militar_logado and not request.user.is_superuser:
        messages.error(request, "Seu usuário não está vinculado a um militar para acessar a chamada.")
        return redirect(request.META.get('HTTP_REFERER', '/'))

    # Se a seção não vier na URL, usaremos os grupos do próprio usuário logado
    secao_url = request.GET.get('secao')

    hoje = date.today()
    
    data_ref_str = request.GET.get('data')
    if data_ref_str:
        try:
            data_ref = datetime.strptime(data_ref_str, '%Y-%m-%d').date()
        except ValueError:
            data_ref = hoje
    else:
        data_ref = hoje

    start_of_week = data_ref - timedelta(days=data_ref.weekday())
    dias_semana = [start_of_week + timedelta(days=i) for i in range(7)]
    semana_anterior = (start_of_week - timedelta(days=7)).strftime('%Y-%m-%d')
    proxima_semana = (start_of_week + timedelta(days=7)).strftime('%Y-%m-%d')

    # Ordem hierárquica (número menor = maior patente)
    rank_order = Case(
        When(posto='CL', then=Value(0)), When(posto='TC', then=Value(1)), When(posto='MJ', then=Value(2)), When(posto='CP', then=Value(3)),
        When(posto='1T', then=Value(4)), When(posto='2T', then=Value(5)),When(posto='ASP', then=Value (6)), When(posto='SO', then=Value(7)),
        When(posto='1S', then=Value(8)), When(posto='2S', then=Value(9)), When(posto='3S', then=Value(10)),
        When(posto='CB', then=Value(11)), When(posto='S1', then=Value(12)), When(posto='S2', then=Value(13)),When(posto='REC', then=Value(14)),
        default=Value(99), output_field=IntegerField(),
    )

    query_efetivo_setor = Q()
    grupos_secao = Group.objects.none()
    nome_setor_exibicao = "Geral"
    base_template = 'Secao_pessoal/base.html'
    
    if secao_url:
        mapa_templates = {
            'ouvidoria': 'base.html',
            'operacoes': 'Secao_operacoes/base.html',
            'informatica': 'informatica/base.html',
            's1': 'Secao_pessoal/base.html'
        }
        base_template = mapa_templates.get(secao_url.lower(), 'Secao_pessoal/base.html')
        
        mapa_nomes_exibicao = {
            'ouvidoria': 'Ouvidoria',
            'operacoes': 'Operações',
            'informatica': 'Informática',
            's1': 'Seção de Pessoal (S1)'
        }
        nome_setor_exibicao = mapa_nomes_exibicao.get(secao_url.lower(), secao_url.capitalize())
        
        mapa_termos_busca = {
            'ouvidoria': ['Ouvidoria'],
            'operacoes': ['Operações', 'Operacoes', 'seção de operação', 'secao de operacao'],
            'informatica': ['Informática', 'Informatica'],
            's1': ['S1', 'Seção de Pessoal', 'Secao de Pessoal', 'Pessoal']
        }
        termos_busca = mapa_termos_busca.get(secao_url.lower(), [secao_url])
        
        query_grupos = Q()
        for termo in termos_busca:
            if termo:
                query_grupos |= Q(name__icontains=termo)
                query_efetivo_setor |= Q(setor__icontains=termo)
        grupos_secao = Group.objects.filter(query_grupos)
    else:
        if not request.user.is_superuser:
            grupos_secao = request.user.groups.all()
            if grupos_secao.exists():
                nome_setor_exibicao = " / ".join([g.name for g in grupos_secao])
                nomes_g_lower = nome_setor_exibicao.lower()
                if 'opera' in nomes_g_lower: base_template = 'Secao_operacoes/base.html'
                elif 'inform' in nomes_g_lower: base_template = 'informatica/base.html'
                elif 'ouvidoria' in nomes_g_lower: base_template = 'base.html'
                else: base_template = 'Secao_pessoal/base.html'
                
                for g in grupos_secao:
                    query_efetivo_setor |= Q(setor__icontains=g.name)
                    if 'S1' in g.name.upper() or 'PESSOAL' in g.name.upper():
                        query_efetivo_setor |= Q(setor__icontains='S1') | Q(setor__icontains='Pessoal')
                    if 'OPERA' in g.name.upper():
                        query_efetivo_setor |= Q(setor__icontains='Operações') | Q(setor__icontains='Operacoes')
            else:
                nome_setor_exibicao = militar_logado.setor if militar_logado else 'Geral'
                if militar_logado and militar_logado.setor:
                    query_efetivo_setor |= Q(setor__icontains=militar_logado.setor)
        else:
            nome_setor_exibicao = "Geral (Todos os Setores)"

    militares_ids_grupo = []
    if grupos_secao.exists():
        # Extração 100% segura usando loop, evitamos FieldErrors em queries complexas com related_names dinâmicos
        for u in get_user_model().objects.filter(groups__in=grupos_secao):
            try:
                m_id = getattr(getattr(u, 'profile', None), 'militar_id', None)
                if m_id:
                    militares_ids_grupo.append(m_id)
            except Exception:
                pass

    filtro_secao = query_efetivo_setor | Q(id__in=militares_ids_grupo)

    # Filtro ultra-tolerante para abranger militares ativos (cobre "ATIVO", "Ativo ", "Pronto", etc.)
    filtro_ativo = Q(situacao__icontains='Ativ') | Q(situacao__exact='') | Q(situacao__isnull=True) | Q(situacao__exact=' ') | Q(situacao__icontains='Pronto')

    # Filtra os militares apenas da seção do usuário logado (se não for admin)
    if request.user.is_superuser and not secao_url and not grupos_secao.exists():
        efetivo = Efetivo.objects.filter(filtro_ativo).annotate(rank_order=rank_order).order_by('rank_order', 'nome_guerra')
        rank_logado = -1 # Admin edita todos
    else:
        efetivo = Efetivo.objects.filter(filtro_ativo & filtro_secao).annotate(rank_order=rank_order).order_by('rank_order', 'nome_guerra').distinct()
        if request.user.is_superuser:
            rank_logado = -1
        else:
            hierarquia = {'CL': 0, 'TC': 1, 'MJ': 2, 'CP': 3, '1T': 4, '2T': 5, 'ASP': 6, 'SO': 7, '1S': 8, '2S': 9, '3S': 10, 'CB': 11, 'S1': 12, 'S2': 13, 'REC': 14}
            rank_logado = hierarquia.get(militar_logado.posto if militar_logado else '', 99)

    # Buscar as presenças/faltas já marcadas na semana
    registros_semana = RegistroChamada.objects.filter(data__range=[dias_semana[0], dias_semana[-1]], militar__in=efetivo)
    
    presencas_dict = {}
    for r in registros_semana:
        if r.militar_id not in presencas_dict:
            presencas_dict[r.militar_id] = {}
        presencas_dict[r.militar_id][r.data.strftime('%Y-%m-%d')] = r.status

    lista_chamada = []
    for m in efetivo:
        pode_editar = rank_logado < m.rank_order  # Pode editar se a patente for maior (número menor)
        presencas_militar = presencas_dict.get(m.id, {})
        status_dias = []
        for dia in dias_semana:
            dia_str = dia.strftime('%Y-%m-%d')
            status_dias.append({
                'data': dia,
                'data_str': dia_str,
                'status': presencas_militar.get(dia_str, None),
                'is_hoje': dia == hoje,
                'is_futuro': dia > hoje
            })

        lista_chamada.append({
            'militar': m,
            'pode_editar': pode_editar,
            'dias': status_dias
        })

    context = {
        'lista_chamada': lista_chamada,
        'dias_semana': dias_semana,
        'hoje': hoje,
        'semana_anterior': semana_anterior,
        'proxima_semana': proxima_semana,
        'setor_nome': nome_setor_exibicao,
        'base_template': base_template,
        'secao': secao_url or 'Geral'
    }
    return render(request, 'chamada/chamada.html', context)

@login_required
@require_POST
def chamada_toggle(request):
    militar_id = request.POST.get('militar_id')
    status_val = request.POST.get('status')
    data_str = request.POST.get('data')
    
    militar_logado = getattr(request.user, 'profile', None) and request.user.profile.militar
    alvo = get_object_or_404(Efetivo, id=militar_id)
    
    if data_str:
        data_chamada = datetime.strptime(data_str, '%Y-%m-%d').date()
    else:
        data_chamada = date.today()

    # Bloqueia a edição de dias futuros para TODOS
    if data_chamada > date.today():
        return JsonResponse({'status': 'error', 'message': 'Não é possível alterar a chamada de dias futuros.'}, status=403)

    # Bloqueia a edição para dias passados (exceto para administradores)
    if data_chamada < date.today() and not request.user.is_superuser:
        return JsonResponse({'status': 'error', 'message': 'Apenas a chamada do dia atual pode ser alterada.'}, status=403)

    # Validação de Hierarquia de Segurança
    if not request.user.is_superuser:
        hierarquia = {'CL': 0, 'TC': 1, 'MJ': 2, 'CP': 3, '1T': 4, '2T': 5, 'ASP': 6, 'SO': 7, '1S': 8, '2S': 9, '3S': 10, 'CB': 11, 'S1': 12, 'S2': 13, 'REC': 14}
        rank_logado = hierarquia.get(militar_logado.posto if militar_logado else '', 99)
        rank_alvo = hierarquia.get(alvo.posto, 99)
        if rank_logado >= rank_alvo:
            return JsonResponse({'status': 'error', 'message': 'Sem permissão para alterar chamada de militar mais antigo ou do mesmo posto.'}, status=403)
        
    registro, created = RegistroChamada.objects.update_or_create(
        data=data_chamada, 
        militar=alvo,
        defaults={'status': status_val}
    )
    
    return JsonResponse({'status': 'success', 'status_val': registro.status, 'data_str': data_chamada.strftime('%Y-%m-%d')})