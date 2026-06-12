from django.shortcuts import render, redirect, get_object_or_404
from django.db import models
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from datetime import date
import json
import os
from django.conf import settings
from .models import Escala, TurnoEscala, PostoEscala, Missao, ItemArmamento, ItemEquipamento, ItemHorario, ConfiguracaoOperacoes, EquipamentoCatalogo, RadioCatalogo, UniformeCatalogo, ArmamentoCatalogo, ACargaOpcao, SituacaoEspecialEfetivo
from .forms import EscalaForm, TurnoEscalaForm, PostoEscalaForm, MissaoForm
from Secao_pessoal.models import Efetivo
from django.contrib.auth import get_user_model
User = get_user_model()

STD_HORARIOS = [
    ('chamada',     'horario_chamada',     'CHAMADA'),
    ('armamento',   'horario_armamento',   'ARMAMENTO'),
    ('alimentacao', 'horario_alimentacao', 'ALIMENTAÇÃO'),
    ('sala_sgt',    'horario_sala_sgt',    'HORÁRIO NA SALA SGT DE DIA AO BINFAE GL'),
    ('saida',       'horario_saida',       'SAÍDA DO BINFAE GL'),
    ('pronto',      'horario_pronto',      'PRONTO NO OBJETIVO'),
]
_STD_MAP = {k: (f, l) for k, f, l in STD_HORARIOS}


def _horarios_form_ctx(missao=None):
    """Returns ordered list of schedule items for the form template."""
    if missao and missao.horarios_config:
        try:
            config = json.loads(missao.horarios_config)
        except (json.JSONDecodeError, ValueError):
            config = []
    else:
        config = [{'tipo': 'padrao', 'key': k} for k, _, _ in STD_HORARIOS]

    extras = list(missao.horarios_extras.all()) if missao else []
    extra_idx = 0
    result = []
    for entry in config:
        key = entry.get('key', '')
        tipo = entry.get('tipo', 'padrao' if key else 'extra')
        if tipo == 'padrao' and key in _STD_MAP:
            field_name, label = _STD_MAP[key]
            v = getattr(missao, field_name, None) if missao else None
            value = v.strftime('%H:%M') if v else ''
            result.append({'tipo': 'padrao', 'key': key, 'label': label,
                           'field_name': field_name, 'value': value})
        elif tipo == 'extra' and extra_idx < len(extras):
            e = extras[extra_idx]
            result.append({'tipo': 'extra', 'label': e.label,
                           'value': e.horario.strftime('%H:%M') if e.horario else ''})
            extra_idx += 1
    while extra_idx < len(extras):
        e = extras[extra_idx]
        result.append({'tipo': 'extra', 'label': e.label,
                       'value': e.horario.strftime('%H:%M') if e.horario else ''})
        extra_idx += 1
    return result


def _horarios_pdf_ctx(missao):
    """Returns ordered list of {label, horario} for the PDF template."""
    if missao.horarios_config:
        try:
            config = json.loads(missao.horarios_config)
        except (json.JSONDecodeError, ValueError):
            config = [{'tipo': 'padrao', 'key': k} for k, _, _ in STD_HORARIOS]
    else:
        config = [{'tipo': 'padrao', 'key': k} for k, _, _ in STD_HORARIOS]

    std_labels = {k: l for k, _, l in STD_HORARIOS}
    std_fields = {k: getattr(missao, f) for k, f, _ in STD_HORARIOS}
    extras = list(missao.horarios_extras.all())
    extra_idx = 0
    result = []
    for entry in config:
        key = entry.get('key', '')
        tipo = entry.get('tipo', 'padrao' if key else 'extra')
        if tipo == 'padrao' and key in std_labels:
            result.append({'label': std_labels[key], 'horario': std_fields[key]})
        elif tipo == 'extra' and extra_idx < len(extras):
            e = extras[extra_idx]
            result.append({'label': e.label, 'horario': e.horario})
            extra_idx += 1
    while extra_idx < len(extras):
        e = extras[extra_idx]
        result.append({'label': e.label, 'horario': e.horario})
        extra_idx += 1
    return result


def _efetivo_ref_from_post(request):
    """Lê os campos hidden _ref_* do POST e retorna dict de referência, ou None."""
    of = request.POST.get('_ref_of', '').strip()
    if not of:
        return None
    def _int(v):
        try: return int(v)
        except: return 0
    return {
        'of':     _int(request.POST.get('_ref_of')),
        'so_sgt': _int(request.POST.get('_ref_so_sgt')),
        'cb':     _int(request.POST.get('_ref_cb')),
        's1':     _int(request.POST.get('_ref_s1')),
        's2':     _int(request.POST.get('_ref_s2')),
        'rec':    _int(request.POST.get('_ref_rec')),
    }


def _get_diretrizes_padrao(config):
    """Retorna lista de textos padrão do config, migrando campos antigos se necessário."""
    if config.diretrizes_padrao_json:
        try:
            return json.loads(config.diretrizes_padrao_json)
        except Exception:
            pass
    # fallback para campos legados
    result = []
    if config.diretriz_padrao_1:
        result.append(config.diretriz_padrao_1)
    if config.diretriz_padrao_2:
        result.append(config.diretriz_padrao_2)
    return result


def _get_diretrizes_missao(missao):
    """Retorna lista de dicts {texto, is_padrao} para a missão."""
    if missao and missao.diretrizes_json:
        try:
            return json.loads(missao.diretrizes_json)
        except Exception:
            pass
    if missao:
        # fallback para campos legados
        result = []
        if missao.diretriz_1:
            result.append({'texto': missao.diretriz_1, 'is_padrao': False})
        if missao.diretriz_2:
            result.append({'texto': missao.diretriz_2, 'is_padrao': False})
        return result
    return []


def _salvar_diretrizes(request, missao):
    textos = request.POST.getlist('diretriz_texto[]')
    padrao_flags = request.POST.getlist('diretriz_is_padrao[]')
    result = []
    for i, txt in enumerate(textos):
        t = txt.strip()
        if t:
            is_p = padrao_flags[i] == '1' if i < len(padrao_flags) else False
            result.append({'texto': t, 'is_padrao': is_p})
    missao.diretrizes_json = json.dumps(result, ensure_ascii=False)
    missao.save(update_fields=['diretrizes_json'])


def _is_sop_operacoes(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name='SOP - Operações').exists()


def _is_sop_escalas(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name='SOP- Escalas').exists()


def _can_see_missoes(user):
    """Pode ver Missões: superuser, staff, SOP - Operações (mas NÃO apenas SOP- Escalas)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name='SOP - Operações').exists()


def _can_see_escalas(user):
    """Pode ver Escalas: superuser, staff, SOP- Escalas (mas NÃO apenas SOP - Operações)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser or user.is_staff:
        return True
    return user.groups.filter(name__in=['SOP- Escalas']).exists()


def sop_required(view_func):
    """Decorator para views de Missões — exige grupo SOP - Operações."""
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not _can_see_missoes(request.user):
            messages.error(request, 'Acesso restrito ao grupo SOP - Operações.')
            return redirect('Secao_operacoes:index')
        return view_func(request, *args, **kwargs)
    return login_required(wrapper)


def escalas_required(view_func):
    """Decorator para views de Escalas — exige grupo SOP- Escalas."""
    from functools import wraps
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not _can_see_escalas(request.user):
            messages.error(request, 'Acesso restrito ao grupo SOP- Escalas.')
            return redirect('Secao_operacoes:index')
        return view_func(request, *args, **kwargs)
    return login_required(wrapper)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_militar_logado(request):
    """Retorna o Efetivo vinculado ao usuário logado, ou o primeiro oficial."""
    if hasattr(request.user, 'profile') and request.user.profile.militar:
        return request.user.profile.militar
    return Efetivo.objects.filter(oficial=True).first()


def _notificar(remetente, destinatario, titulo, mensagem):
    """Cria Notificacao no novo sistema unificado."""
    if not (remetente and destinatario):
        return
    try:
        from notificacoes.utils import notificar
        dest_user = User.objects.filter(profile__militar=destinatario).first()
        if dest_user:
            notificar(dest_user, titulo, corpo=mensagem, tipo='sistema')
    except Exception:
        pass


def _notificar_esi_sobre_missao(missao):
    """Notifica grupo ESI-Missões (sino + caixa de entrada) quando uma missão os envolve."""
    campos_esi = (missao.cmt_a_cargo or '') + (missao.mot_a_cargo or '') + (missao.equipe_a_cargo or '')
    if 'ESI' not in campos_esi.upper():
        return
    try:
        from notificacoes.utils import notificar
        from django.urls import reverse
        # Notifica o grupo ESI-Missões (e ESI completo por segurança)
        usuarios_esi = User.objects.filter(
            groups__name__in=['ESI-Missões', 'ESI']
        ).distinct()
        if not usuarios_esi.exists():
            return
        url_escala = reverse('ESI:missao_escala', args=[missao.pk])
        titulo = f"Nova missão ESI: OMIS N° {missao.numero}/SOPBINFAEGL/BINFAE GL"
        corpo = f"{missao.nome_missao} — {missao.data_missao.strftime('%d/%m/%Y')}"
        # Sino de notificações
        notificar(usuarios_esi, titulo=titulo, corpo=corpo, url=url_escala, tipo='sistema')
        # Caixa de entrada — remetente é o usuário do sistema (criado_por)
        try:
            from caixa_entrada.models import Mensagem
            remetente = missao.criado_por
            if remetente:
                msg = Mensagem.objects.create(
                    remetente=remetente,
                    assunto=titulo,
                    corpo=(
                        f"A missão {corpo} foi atribuída à ESI.\n\n"
                        f"Campos:\n"
                        f"  CMT a cargo: {missao.cmt_a_cargo or '—'}\n"
                        f"  MOT a cargo: {missao.mot_a_cargo or '—'}\n"
                        f"  Equipe a cargo: {missao.equipe_a_cargo or '—'}\n\n"
                        f"Acesse o sistema para escalar os militares."
                    ),
                    tipo='mensagem',
                )
                msg.destinatarios.set(usuarios_esi)
        except Exception:
            pass
    except Exception:
        pass


# ── Views ────────────────────────────────────────────────────────────────────

@login_required
def index(request):
    return render(request, 'Secao_operacoes/base.html')


@escalas_required
def escala_list(request):
    from django.db.models import Q
    search_query = request.GET.get('q', '')
    hoje = date.today()

    escalas = Escala.objects.all().order_by('nome')

    resultados_turnos = []
    escalas_encontradas = []
    if search_query:
        resultados_turnos = TurnoEscala.objects.filter(
            Q(militar__nome_guerra__icontains=search_query) |
            Q(posto__nome__icontains=search_query)
        ).select_related('escala', 'militar', 'posto').order_by('data')

        escalas_encontradas = Escala.objects.filter(
            nome__icontains=search_query
        ).order_by('nome')

    for escala in escalas:
        escala.turnos_hoje = escala.turnos.filter(data=hoje).select_related('militar', 'posto')

    return render(request, 'Secao_operacoes/escala_list.html', {
        'escalas': escalas,
        'resultados_turnos': resultados_turnos,
        'escalas_encontradas': escalas_encontradas,
        'search_query': search_query,
        'hoje': hoje,
    })


@escalas_required
def escala_create(request):
    if request.method == 'POST':
        form = EscalaForm(request.POST)
        if form.is_valid():
            escala = form.save()
            # Notifica os militares adicionados na criação
            militar_logado = _get_militar_logado(request)
            for militar in escala.militares.all():
                _notificar(
                    remetente=militar_logado,
                    destinatario=militar,
                    titulo=f"Inclusão na Escala — {escala.nome}",
                    mensagem=(
                        f"Você foi adicionado à escala de serviço \"{escala.nome}\". "
                        f"A partir de agora você poderá ser escalado para os turnos desta escala. "
                        f"Adicionado por: {militar_logado.nome_guerra if militar_logado else 'Sistema'}."
                    )
                )
            messages.success(request, 'Escala criada com sucesso!')
            return redirect('Secao_operacoes:escala_detail', pk=escala.pk)
    else:
        form = EscalaForm()
    return render(request, 'Secao_operacoes/escala_form.html', {'form': form, 'title': 'Nova Escala'})


@escalas_required
def escala_edit(request, pk):
    escala = get_object_or_404(Escala, pk=pk)
    if request.method == 'POST':
        # Captura militares antes de salvar para comparar depois
        militares_antes = set(escala.militares.values_list('id', flat=True))

        form = EscalaForm(request.POST, instance=escala)
        if form.is_valid():
            form.save()

            militares_depois = set(escala.militares.values_list('id', flat=True))
            militar_logado = _get_militar_logado(request)

            adicionados = militares_depois - militares_antes
            removidos = militares_antes - militares_depois

            # Busca todos os militares afetados em 1 query (evita N+1)
            militares_map = {
                m.pk: m
                for m in Efetivo.objects.filter(pk__in=adicionados | removidos)
            }

            for mid in adicionados:
                dest = militares_map.get(mid)
                if dest:
                    _notificar(
                        remetente=militar_logado,
                        destinatario=dest,
                        titulo=f"Inclusão na Escala — {escala.nome}",
                        mensagem=(
                            f"Você foi adicionado à escala de serviço \"{escala.nome}\". "
                            f"A partir de agora você poderá ser escalado para os turnos desta escala. "
                            f"Adicionado por: {militar_logado.nome_guerra if militar_logado else 'Sistema'}."
                        )
                    )

            for mid in removidos:
                dest = militares_map.get(mid)
                if dest:
                    _notificar(
                        remetente=militar_logado,
                        destinatario=dest,
                        titulo=f"Remoção da Escala — {escala.nome}",
                        mensagem=(
                            f"Você foi removido da escala de serviço \"{escala.nome}\" e não faz mais parte desta equipe. "
                            f"Removido por: {militar_logado.nome_guerra if militar_logado else 'Sistema'}."
                        )
                    )

            messages.success(request, 'Escala atualizada com sucesso!')
            return redirect('Secao_operacoes:escala_detail', pk=escala.pk)
    else:
        form = EscalaForm(instance=escala)

    posto_form = PostoEscalaForm()
    postos = escala.postos.all()
    return render(request, 'Secao_operacoes/escala_form.html', {
        'form': form,
        'title': 'Editar Escala',
        'escala': escala,
        'posto_form': posto_form,
        'postos': postos,
    })


@escalas_required
def escala_delete(request, pk):
    escala = get_object_or_404(Escala, pk=pk)
    if request.method == 'POST':
        nome = escala.nome
        escala.delete()
        messages.success(request, f'Escala "{nome}" excluída com sucesso.')
        return redirect('Secao_operacoes:escala_list')
    return redirect('Secao_operacoes:escala_list')


@escalas_required
def escala_toggle_ativo(request, pk):
    escala = get_object_or_404(Escala, pk=pk)
    if request.method == 'POST':
        escala.ativo = not escala.ativo
        escala.save()
        status = "ativada" if escala.ativo else "desativada"
        messages.success(request, f'Escala "{escala.nome}" {status} com sucesso.')
    return redirect('Secao_operacoes:escala_list')


@escalas_required
def escala_detail(request, pk):
    escala = get_object_or_404(Escala, pk=pk)
    hoje = date.today()

    if request.method == 'POST':
        form = TurnoEscalaForm(request.POST, escala_id=escala.pk)
        if form.is_valid():
            turno = form.save(commit=False)
            turno.escala = escala
            turno.save()

            militar_logado = _get_militar_logado(request)
            posto_str = f" no posto {turno.posto.nome}" if turno.posto else ""
            _notificar(
                remetente=militar_logado,
                destinatario=turno.militar,
                titulo=f"Escala de Serviço — {escala.nome}",
                mensagem=(
                    f"Você foi escalado para o serviço de \"{escala.nome}\"{posto_str} "
                    f"no dia {turno.data.strftime('%d/%m/%Y')}. "
                    f"Escalado por: {militar_logado.nome_guerra if militar_logado else 'Sistema'}."
                )
            )

            messages.success(request, f'{turno.militar.nome_guerra} escalado para {turno.data.strftime("%d/%m/%Y")}!')
            return redirect('Secao_operacoes:escala_detail', pk=escala.pk)
    else:
        form = TurnoEscalaForm(escala_id=escala.pk)

    import json
    from collections import defaultdict

    todos_turnos = escala.turnos.all().select_related('militar', 'posto').order_by('data')
    turnos_futuros = [t for t in todos_turnos if t.data >= hoje]
    turnos_passados = [t for t in todos_turnos if t.data < hoje]
    turnos_passados.sort(key=lambda t: t.data, reverse=True)

    # Mapa de postos ocupados por data: {posto_id: [date_str, ...]}
    postos_ocupados = defaultdict(list)
    for t in todos_turnos:
        if t.posto_id:
            postos_ocupados[str(t.posto_id)].append(t.data.isoformat())
    postos_ocupados_json = json.dumps(dict(postos_ocupados))

    return render(request, 'Secao_operacoes/escala_detail.html', {
        'escala': escala,
        'form': form,
        'turnos_futuros': turnos_futuros,
        'turnos_passados': turnos_passados,
        'hoje': hoje,
        'postos_ocupados_json': postos_ocupados_json,
    })


@escalas_required
def turno_delete(request, pk):
    turno = get_object_or_404(TurnoEscala, pk=pk)
    escala_pk = turno.escala.pk
    hoje = date.today()
    if request.method == 'POST':
        if turno.data < hoje:
            messages.error(request, 'Não é possível remover turnos de dias já passados.')
        else:
            militar = turno.militar
            escala = turno.escala
            posto_str = f" do posto {turno.posto.nome}" if turno.posto else ""
            data_str = turno.data.strftime('%d/%m/%Y')

            turno.delete()

            militar_logado = _get_militar_logado(request)
            _notificar(
                remetente=militar_logado,
                destinatario=militar,
                titulo=f"Remoção de Turno — {escala.nome}",
                mensagem=(
                    f"Seu turno de serviço{posto_str} na escala \"{escala.nome}\" "
                    f"do dia {data_str} foi cancelado. "
                    f"Removido por: {militar_logado.nome_guerra if militar_logado else 'Sistema'}."
                )
            )

            messages.success(request, f'Turno de {militar.nome_guerra} em {data_str} removido.')
    return redirect('Secao_operacoes:escala_detail', pk=escala_pk)


@escalas_required
def turno_delete_all(request, pk):
    escala = get_object_or_404(Escala, pk=pk)
    if request.method == 'POST':
        hoje = date.today()
        qs = escala.turnos.filter(data__gte=hoje).select_related('militar', 'posto')
        militar_logado = _get_militar_logado(request)

        # Notifica cada militar antes de deletar
        militares_notificados = set()
        for turno in qs:
            if turno.militar.pk not in militares_notificados:
                _notificar(
                    remetente=militar_logado,
                    destinatario=turno.militar,
                    titulo=f"Remoção de Turnos — {escala.nome}",
                    mensagem=(
                        f"Todos os seus turnos futuros na escala \"{escala.nome}\" foram cancelados. "
                        f"Removido por: {militar_logado.nome_guerra if militar_logado else 'Sistema'}."
                    )
                )
                militares_notificados.add(turno.militar.pk)

        count = qs.count()
        qs.delete()
        messages.success(request, f'{count} turno(s) futuro(s) removido(s) com sucesso!')
    return redirect('Secao_operacoes:escala_detail', pk=escala.pk)


@escalas_required
def posto_create(request, escala_pk):
    escala = get_object_or_404(Escala, pk=escala_pk)
    if request.method == 'POST':
        form = PostoEscalaForm(request.POST)
        if form.is_valid():
            posto = form.save(commit=False)
            posto.escala = escala
            posto.save()
            messages.success(request, f'Posto "{posto.nome}" adicionado à escala.')
        else:
            messages.error(request, 'Nome do posto inválido.')
    return redirect('Secao_operacoes:escala_edit', pk=escala_pk)


@escalas_required
def posto_delete(request, pk):
    posto = get_object_or_404(PostoEscala, pk=pk)
    escala_pk = posto.escala.pk
    if request.method == 'POST':
        nome = posto.nome
        posto.delete()
        messages.success(request, f'Posto "{nome}" removido.')
    return redirect('Secao_operacoes:escala_edit', pk=escala_pk)


@escalas_required
def api_escala_eventos(request, pk):
    from datetime import timedelta
    escala = get_object_or_404(Escala, pk=pk)
    turnos = escala.turnos.all().select_related('militar', 'posto')

    TIPO_COLORS = {
        '24h':        '#0d6efd',
        'turno':      '#0ea5e9',
        'permanencia': '#8b5cf6',
        'sbv':        '#f59e0b',
    }
    color = TIPO_COLORS.get(escala.tipo, '#0d6efd')

    eventos = []
    for turno in turnos:
        titulo = turno.militar.nome_guerra
        posto_nome = ''
        horario_str = ''

        if turno.posto:
            posto_nome = turno.posto.nome
            horario_str = turno.posto.horario or ''
            label = posto_nome
            if horario_str:
                label += f' {horario_str}'
            titulo += f' ({label})'

        evento = {
            'id': turno.id,
            'title': titulo,
            'start': turno.data.isoformat(),
            'allDay': True,
            'description': turno.observacao or '',
            'posto': posto_nome,
            'horario': horario_str,
            'tipo': escala.tipo,
            'color': color,
        }

        # 24h: event bar spans into the next day
        if escala.tipo == '24h':
            evento['end'] = (turno.data + timedelta(days=1)).isoformat()

        # permanencia: span by duracao_horas if set
        elif escala.tipo == 'permanencia' and escala.duracao_horas:
            dias_extra = escala.duracao_horas // 24
            if dias_extra >= 1:
                evento['end'] = (turno.data + timedelta(days=dias_extra)).isoformat()

        eventos.append(evento)
    return JsonResponse(eventos, safe=False)


# ── Missões (OMIS) ────────────────────────────────────────────────────────────

@sop_required
def missao_list(request):
    from django.db.models import Q
    import datetime as dt
    hoje = date.today()
    data_filtro = request.GET.get('data', '')
    filtro_hoje = request.GET.get('hoje', '')
    filtro_semana = request.GET.get('semana', '')
    busca = request.GET.get('q', '').strip()
    ordem = request.GET.get('ordem', 'desc')
    ano = request.GET.get('ano', str(date.today().year))

    missoes = Missao.objects.all().select_related('cmt_missao').prefetch_related('escala_esi__militares')

    semana_inicio = semana_fim = None

    if busca:
        try:
            num = int(busca)
            missoes = missoes.filter(Q(numero=num) | Q(nome_missao__icontains=busca))
        except ValueError:
            missoes = missoes.filter(nome_missao__icontains=busca)
    elif filtro_hoje:
        missoes = missoes.filter(data_missao=hoje)
        data_filtro = hoje.strftime('%Y-%m-%d')
    elif filtro_semana:
        # filtro_semana pode ser 'atual' ou uma data no formato 'YYYY-WNN' (semana ISO)
        try:
            if filtro_semana == 'atual':
                ref = hoje
            else:
                ref = dt.datetime.strptime(filtro_semana + '-1', '%Y-W%W-%w').date()
            semana_inicio = ref - dt.timedelta(days=ref.weekday())
            semana_fim = semana_inicio + dt.timedelta(days=6)
            missoes = missoes.filter(data_missao__range=(semana_inicio, semana_fim))
        except (ValueError, TypeError):
            filtro_semana = ''
    elif data_filtro:
        try:
            d = dt.datetime.strptime(data_filtro, '%Y-%m-%d').date()
            missoes = missoes.filter(data_missao=d)
        except ValueError:
            data_filtro = ''

    # Filtro de ano — ativo apenas quando nenhum filtro de data explícito está em uso
    if not busca and not data_filtro and not filtro_hoje and not filtro_semana:
        try:
            missoes = missoes.filter(data_missao__year=int(ano))
        except (ValueError, TypeError):
            pass

    if ordem == 'asc':
        missoes = missoes.order_by('numero')
    else:
        missoes = missoes.order_by('-numero')

    # semana atual para pré-preencher o input week
    semana_atual_value = hoje.strftime('%Y-W%W')

    from django.core.paginator import Paginator
    paginator = Paginator(missoes, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    anos_disponiveis = sorted(set(
        Missao.objects.dates('data_missao', 'year').values_list('data_missao__year', flat=True)
    ), reverse=True)
    ano_atual_str = str(date.today().year)

    return render(request, 'Secao_operacoes/missao_list.html', {
        'missoes': page_obj.object_list,
        'page_obj': page_obj,
        'data_filtro': data_filtro,
        'filtro_hoje': bool(filtro_hoje),
        'filtro_semana': filtro_semana,
        'semana_inicio': semana_inicio,
        'semana_fim': semana_fim,
        'hoje': hoje.strftime('%Y-%m-%d'),
        'busca': busca,
        'ordem': ordem,
        'semana_atual_value': semana_atual_value,
        'ano': ano,
        'anos_disponiveis': anos_disponiveis,
        'ano_atual_str': ano_atual_str,
    })


@sop_required
def missao_create(request):
    origem = None
    efetivo_ref = None
    from django.utils import timezone as _tz_create
    if request.method == 'POST':
        form = MissaoForm(request.POST)
        efetivo_ref = _efetivo_ref_from_post(request)
        if form.is_valid():
            missao = form.save(commit=False)
            missao.criado_por = request.user
            missao.data_emissao = _tz_create.localdate()
            missao.radio_nome = request.POST.get('radio_nome', '').strip()
            _salvar_efetivo_post(request, missao)
            missao.save()
            _salvar_equipe_post(request, missao)
            _salvar_horarios(request, missao)
            _salvar_diretrizes(request, missao)
            _salvar_armamentos_equipamentos(request, missao)
            messages.success(request, f'OMIS Nº {missao.numero} criada com sucesso.')
            _notificar_esi_sobre_missao(missao)
            return redirect('Secao_operacoes:missao_detail', pk=missao.pk)
    else:
        _ano_atual = _tz_create.localdate().year
        proximo = (
            Missao.objects.filter(data_emissao__year=_ano_atual)
            .aggregate(m=models.Max('numero'))['m'] or 0
        ) + 1
        cfg = ConfiguracaoOperacoes.get_instance()
        origem = None
        efetivo_ref = None
        copiar_de = request.GET.get('copiar_de')
        if copiar_de:
            try:
                origem = Missao.objects.get(pk=copiar_de)
                efetivo_ref = {
                    'of': origem.efetivo_of,
                    'so_sgt': origem.efetivo_so_sgt,
                    'cb': origem.efetivo_cb,
                    's1': origem.efetivo_s1,
                    's2': origem.efetivo_s2,
                    'rec': origem.efetivo_rec,
                }
                form = MissaoForm(initial={
                    'numero': proximo,
                    'nome_missao': origem.nome_missao,
                    'local': origem.local,
                    'transporte': origem.transporte,
                    'uniforme': origem.uniforme,
                    'acionador': origem.acionador,
                    'objetivo': origem.objetivo,
                    'endereco': origem.endereco,
                    'observacoes_armamento': origem.observacoes_armamento,
                    'radio_nome': origem.radio_nome,
                    'radio_qtd': origem.radio_qtd,
                    'radio_canal': origem.radio_canal,
                })
            except Missao.DoesNotExist:
                origem = None
        if not origem:
            form = MissaoForm(initial={
                'numero': proximo,
                'observacoes_armamento': cfg.observacoes_armamento_padrao,
            })
    cfg = ConfiguracaoOperacoes.get_instance()
    diretrizes_padrao = _get_diretrizes_padrao(cfg)
    diretrizes_iniciais = [{'texto': t, 'is_padrao': True} for t in diretrizes_padrao]
    if origem:
        diretrizes_iniciais = _get_diretrizes_missao(origem)
    if origem and origem.efetivo_grupos_json:
        grupos_iniciais = json.loads(origem.efetivo_grupos_json)
    elif origem:
        grupos_iniciais = _build_grupos_from_old_fields(origem)
    else:
        grupos_iniciais = [{'label': 'CMT', 'membros': []}, {'label': 'MOT', 'membros': []}, {'label': 'EQUIPE', 'membros': []}]
    return render(request, 'Secao_operacoes/missao_form.html', {
        'form': form,
        'title': f'Copiar OMIS Nº {origem.numero}' if origem else 'Nova Missão (OMIS)',
        'efetivo_json': _efetivo_json_ctx(),
        'diretrizes_iniciais': diretrizes_iniciais,
        'diretrizes_padrao_json': diretrizes_padrao,
        'obs_armamento_padrao': cfg.observacoes_armamento_padrao,
        'horarios_form': _horarios_form_ctx(None),
        'std_horarios_disponiveis': STD_HORARIOS,
        'efetivo_ref': efetivo_ref,
        'acarga_opcoes_json': json.dumps(list(ACargaOpcao.objects.values('id', 'nome')), ensure_ascii=False),
        'grupos_iniciais_json': json.dumps(grupos_iniciais, ensure_ascii=False),
    })


@sop_required
def missao_edit(request, pk):
    missao = get_object_or_404(Missao, pk=pk)
    efetivo_ref = None
    if request.method == 'POST':
        efetivo_ref = _efetivo_ref_from_post(request)
        form = MissaoForm(request.POST, instance=missao)
        if form.is_valid():
            from django.utils import timezone
            missao = form.save(commit=False)
            missao.data_emissao = timezone.localdate()
            missao.radio_nome = request.POST.get('radio_nome', '').strip()
            _salvar_efetivo_post(request, missao)
            missao.save()
            _salvar_equipe_post(request, missao)
            _salvar_horarios(request, missao)
            _salvar_diretrizes(request, missao)
            missao.armamentos.all().delete()
            missao.equipamentos.all().delete()
            _salvar_armamentos_equipamentos(request, missao)
            messages.success(request, 'Missão atualizada com sucesso.')
            _notificar_esi_sobre_missao(missao)
            return redirect('Secao_operacoes:missao_detail', pk=missao.pk)
    else:
        form = MissaoForm(instance=missao)
    if missao.efetivo_grupos_json:
        grupos_iniciais = json.loads(missao.efetivo_grupos_json)
    else:
        grupos_iniciais = _build_grupos_from_old_fields(missao)
    cfg = ConfiguracaoOperacoes.get_instance()
    diretrizes_padrao = _get_diretrizes_padrao(cfg)
    return render(request, 'Secao_operacoes/missao_form.html', {
        'form': form, 'title': 'Editar Missão', 'missao': missao,
        'efetivo_json': _efetivo_json_ctx(),
        'diretrizes_iniciais': _get_diretrizes_missao(missao),
        'diretrizes_padrao_json': diretrizes_padrao,
        'obs_armamento_padrao': cfg.observacoes_armamento_padrao,
        'horarios_form': _horarios_form_ctx(missao),
        'std_horarios_disponiveis': STD_HORARIOS,
        'efetivo_ref': efetivo_ref,
        'acarga_opcoes_json': json.dumps(list(ACargaOpcao.objects.values('id', 'nome')), ensure_ascii=False),
        'grupos_iniciais_json': json.dumps(grupos_iniciais, ensure_ascii=False),
    })


@sop_required
def missao_detail(request, pk):
    missao = get_object_or_404(Missao, pk=pk)
    config = ConfiguracaoOperacoes.get_instance()
    from informatica.models import ConfiguracaoComandantes
    config_cmds = ConfiguracaoComandantes.get_instance()
    grupos_efetivo = _grupos_efetivo_para_pdf(missao)
    return render(request, 'Secao_operacoes/missao_detail.html', {
        'missao': missao,
        'config': config,
        'config_cmds': config_cmds,
        'grupos_efetivo': grupos_efetivo,
    })


@sop_required
def missao_delete(request, pk):
    missao = get_object_or_404(Missao, pk=pk)
    if request.method == 'POST':
        numero = missao.numero
        missao.delete()
        messages.success(request, f'OMIS Nº {numero} excluída com sucesso.')
        return redirect('Secao_operacoes:missao_list')
    return redirect('Secao_operacoes:missao_list')


@sop_required
def horario_add(request, pk):
    """AJAX: adiciona um horário extra (ou vinculado a slot) a uma missão."""
    from django.views.decorators.http import require_POST as _rp
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    missao = get_object_or_404(Missao, pk=pk)
    label    = request.POST.get('label', '').strip()
    horario  = request.POST.get('horario', '').strip() or None
    slot_key = request.POST.get('slot_key', '').strip()
    if not label:
        return JsonResponse({'ok': False, 'error': 'label obrigatório'}, status=400)
    ordem = ItemHorario.objects.filter(missao=missao).count()
    h = ItemHorario.objects.create(
        missao=missao, label=label, horario=horario, ordem=ordem, slot_key=slot_key
    )
    return JsonResponse({'ok': True, 'id': h.id})


@sop_required
def horario_delete(request, pk, h_id):
    """AJAX: remove um horário extra de uma missão."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)
    h = get_object_or_404(ItemHorario, pk=h_id, missao__pk=pk)
    h.delete()
    return JsonResponse({'ok': True})


@sop_required
def painel_missoes(request):
    """Painel de missões — resumo visual com gráficos, filtros e exportação."""
    from django.db.models import Q, Count
    from django.utils import timezone
    import datetime as dt
    hoje = timezone.localdate()
    filtro  = request.GET.get('filtro', 'proximas')
    busca   = request.GET.get('q', '').strip()
    data_de = request.GET.get('data_de', '').strip()
    data_ate = request.GET.get('data_ate', '').strip()

    esi_q = Q(cmt_a_cargo__icontains='ESI') | Q(mot_a_cargo__icontains='ESI') | Q(equipe_a_cargo__icontains='ESI')

    missoes = Missao.objects.select_related('cmt_missao').prefetch_related('escala_esi__militares')

    if filtro == 'proximas':
        missoes = missoes.filter(data_missao__gte=hoje)
    elif filtro == 'passadas':
        missoes = missoes.filter(data_missao__lt=hoje)
    elif filtro == 'esi':
        missoes = missoes.filter(esi_q)

    if busca:
        try:
            num = int(busca)
            missoes = missoes.filter(Q(numero=num) | Q(nome_missao__icontains=busca))
        except ValueError:
            missoes = missoes.filter(nome_missao__icontains=busca)

    if data_de:
        try:
            missoes = missoes.filter(data_missao__gte=dt.datetime.strptime(data_de, '%Y-%m-%d').date())
        except ValueError:
            data_de = ''
    if data_ate:
        try:
            missoes = missoes.filter(data_missao__lte=dt.datetime.strptime(data_ate, '%Y-%m-%d').date())
        except ValueError:
            data_ate = ''

    total      = Missao.objects.count()
    proximas_n = Missao.objects.filter(data_missao__gte=hoje).count()
    passadas_n = Missao.objects.filter(data_missao__lt=hoje).count()
    com_esi_n  = Missao.objects.filter(esi_q).count()

    # Dados para gráfico de barras — missões por mês no ano corrente
    MESES = ['Jan','Fev','Mar','Abr','Mai','Jun','Jul','Ago','Set','Out','Nov','Dez']
    contagem_meses = [0] * 12
    for m in Missao.objects.filter(data_missao__year=hoje.year).values('data_missao__month').annotate(n=Count('id')):
        contagem_meses[m['data_missao__month'] - 1] = m['n']
    missoes_por_mes_json = json.dumps({'labels': MESES, 'values': contagem_meses})

    missoes = missoes.order_by('data_missao', 'numero')
    return render(request, 'Secao_operacoes/painel_missoes.html', {
        'missoes': missoes,
        'filtro': filtro,
        'busca': busca,
        'data_de': data_de,
        'data_ate': data_ate,
        'hoje': hoje,
        'total': total,
        'proximas_n': proximas_n,
        'passadas_n': passadas_n,
        'com_esi_n': com_esi_n,
        'missoes_por_mes_json': missoes_por_mes_json,
    })


def _grupos_efetivo_para_pdf(missao):
    """Retorna lista de grupos com nomes resolvidos para o PDF."""
    # Pre-carrega militares da ESI (se existir escala)
    esi_militares = []
    try:
        esi_militares = list(missao.escala_esi.militares.order_by('posto', 'nome_guerra'))
    except Exception:
        pass

    # Lê grupos por função da escala ESI (se existir)
    esi_grupos_map = {}  # {label_upper: {'militares': [Efetivo], 'modo': str}}
    try:
        if missao.escala_esi.grupos_json:
            for g in json.loads(missao.escala_esi.grupos_json):
                ids = g.get('militares', [])
                efs = list(Efetivo.objects.filter(pk__in=ids).order_by('posto', 'nome_guerra'))
                esi_grupos_map[g['label'].upper()] = {
                    'militares': efs,
                    'modo': g.get('modo', 'anexo'),
                }
    except Exception:
        pass

    def _membros_da_secao(acargo, label):
        if not acargo:
            return None
        ac = acargo.lower()
        if 'esi' in ac:
            per_grupo = esi_grupos_map.get(label.upper())
            if per_grupo is not None:
                # modo "omis" → expõe militares direto na OMIS
                # modo "anexo" → só no Anexo ESI, OMIS mostra só texto "a cargo de"
                if per_grupo['modo'] == 'omis':
                    return [{'efetivo': e, 'nome': f"{e.posto} {e.nome_guerra}".strip(), 'texto': ''} for e in per_grupo['militares']]
                else:
                    return []
            # Sem grupos específicos: usa todos da ESI (comportamento legado)
            return [{'efetivo': e, 'nome': f"{e.posto} {e.nome_guerra}".strip(), 'texto': ''} for e in esi_militares]
        return []  # seção sem sistema de escala — mostra só texto acargo

    if missao.efetivo_grupos_json:
        try:
            grupos_raw = json.loads(missao.efetivo_grupos_json)
        except (json.JSONDecodeError, ValueError):
            grupos_raw = []
        todos_ids = [m['efetivo_id'] for g in grupos_raw for m in g.get('membros', []) if m.get('efetivo_id')]
        ef_map = {e.pk: e for e in Efetivo.objects.filter(pk__in=todos_ids)}
        grupos = []
        for g in grupos_raw:
            acargo = g.get('acargo', '')
            secao_membros = _membros_da_secao(acargo, g.get('label', '')) if acargo else None
            if secao_membros is not None:
                # Grupo a cargo de uma seção: mostra os militares que ELA escalou
                membros = secao_membros
            else:
                # Sem acargo: mostra os membros manuais
                membros = []
                for m in g.get('membros', []):
                    ef = ef_map.get(m.get('efetivo_id')) if m.get('efetivo_id') else None
                    membros.append({
                        'efetivo': ef,
                        'nome': f"{ef.posto} {ef.nome_guerra}".strip() if ef else '',
                        'texto': m.get('texto', ''),
                    })
            grupos.append({'label': g.get('label', ''), 'membros': membros, 'acargo': acargo})
        return grupos
    # Fallback para campos antigos
    grupos = _build_grupos_from_old_fields_pdf(missao)
    for g in grupos:
        if g.get('acargo'):
            secao_membros = _membros_da_secao(g['acargo'], g.get('label', ''))
            if secao_membros is not None:
                g['membros'] = secao_membros
    return grupos


def _build_grupos_from_old_fields_pdf(missao):
    grupos = []
    cmt_membros = []
    if missao.cmt_missao:
        cmt_membros.append({'efetivo': missao.cmt_missao, 'nome': f"{missao.cmt_missao.posto} {missao.cmt_missao.nome_guerra}", 'texto': ''})
    grupos.append({'label': 'CMT', 'membros': cmt_membros, 'acargo': missao.cmt_a_cargo or ''})

    mot_membros = []
    if missao.motorista:
        mot_membros.append({'efetivo': missao.motorista, 'nome': f"{missao.motorista.posto} {missao.motorista.nome_guerra}", 'texto': ''})
    grupos.append({'label': 'MOT', 'membros': mot_membros, 'acargo': missao.mot_a_cargo or ''})

    eq_membros = [{'efetivo': e, 'nome': f"{e.posto} {e.nome_guerra}", 'texto': ''} for e in missao.equipe.all().order_by('posto', 'nome_guerra')]
    grupos.append({'label': 'EQUIPE', 'membros': eq_membros, 'acargo': missao.equipe_a_cargo or ''})
    return grupos


def _missao_pdf_context(missao, request):
    """Retorna o contexto necessário para renderizar o PDF de uma missão."""
    armas = list(missao.armamentos.all())
    equips = list(missao.equipamentos.all())
    max_linhas = max(len(armas), (len(equips) + 1) // 2, 4)
    linhas_arma_equip = []
    for i in range(max_linhas):
        linhas_arma_equip.append({
            'arma': armas[i] if i < len(armas) else None,
            'eq1':  equips[i * 2]     if i * 2 < len(equips) else None,
            'eq2':  equips[i * 2 + 1] if i * 2 + 1 < len(equips) else None,
        })
    grupos_efetivo = _grupos_efetivo_para_pdf(missao)
    # Mantém equipe_por_posto para backward compat com template antigo
    from collections import defaultdict
    grupos_equipe = defaultdict(list)
    ordem_postos = []
    for e in missao.equipe.all().order_by('posto', 'nome_guerra'):
        if e.posto not in grupos_equipe:
            ordem_postos.append(e.posto)
        grupos_equipe[e.posto].append(e.nome_guerra)
    equipe_por_posto = [(posto, grupos_equipe[posto]) for posto in ordem_postos]
    try:
        from ESI.models import EscalaMissaoESI  # noqa
        from ESI.views import _build_paginas
        escala_esi = missao.escala_esi
        militares_esi = list(escala_esi.militares.order_by('posto', 'nome_guerra'))
    except Exception:
        escala_esi = None
        militares_esi = []
        _build_paginas = None
    esi_paginas, esi_num_paginas = _build_paginas(militares_esi) if _build_paginas else ([], 0)
    config = ConfiguracaoOperacoes.get_instance()
    from informatica.models import ConfiguracaoComandantes
    config_cmds = ConfiguracaoComandantes.get_instance()
    return {
        'missao': missao,
        'config': config,
        'config_cmds': config_cmds,
        'linhas_arma_equip': linhas_arma_equip,
        'grupos_efetivo': grupos_efetivo,
        'equipe_por_posto': equipe_por_posto,
        'horarios_ordenados': _horarios_pdf_ctx(missao),
        'diretrizes': _get_diretrizes_missao(missao),
        'tem_armamento': missao.armamentos.exists(),
        'escala_esi': escala_esi,
        'militares_esi': militares_esi,
        'esi_paginas': esi_paginas,
        'esi_num_paginas': esi_num_paginas,
        'esi_brasao_url': 'file://' + os.path.join(settings.STATIC_ROOT, 'img', 'brasao.png'),
    }


@sop_required
def missao_pdf(request, pk):
    from django.template.loader import render_to_string
    from weasyprint import HTML
    missao = get_object_or_404(Missao, pk=pk)
    ctx = _missao_pdf_context(missao, request)
    html_string = render_to_string('Secao_operacoes/missao_pdf.html', ctx, request=request)
    pdf = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'filename="OMIS_{missao.numero}.pdf"'
    return response


@login_required
def compilado_missoes_pdf(request):
    from django.template.loader import render_to_string
    from weasyprint import HTML
    import datetime

    data_str = request.GET.get('data', '')
    try:
        data = datetime.date.fromisoformat(data_str)
    except ValueError:
        return HttpResponse('Data inválida. Use ?data=AAAA-MM-DD', status=400)

    missoes = Missao.objects.filter(data_missao=data).order_by('numero')
    if not missoes.exists():
        return HttpResponse('Nenhuma missão encontrada nesta data.', status=404)

    base_url = request.build_absolute_uri('/')
    documents = []
    for missao in missoes:
        ctx = _missao_pdf_context(missao, request)
        html_string = render_to_string('Secao_operacoes/missao_pdf.html', ctx, request=request)
        doc = HTML(string=html_string, base_url=base_url).render()
        documents.append(doc)

    all_pages = [page for doc in documents for page in doc.pages]
    pdf = documents[0].copy(all_pages).write_pdf()

    response = HttpResponse(pdf, content_type='application/pdf')
    data_fmt = data.strftime('%d-%m-%Y')
    response['Content-Disposition'] = f'filename="Compilado_Missoes_{data_fmt}.pdf"'
    return response


@login_required
def extrato_missao_pdf(request):
    from django.template.loader import render_to_string
    from weasyprint import HTML
    from datetime import date as date_type
    import datetime

    data_str = request.GET.get('data', '')
    try:
        data = datetime.datetime.strptime(data_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        data = date_type.today()

    missoes = Missao.objects.filter(data_missao=data).order_by('horario_chamada', 'numero')

    data_exibicao = data.strftime('%d/%m/%Y')

    html_string = render_to_string('Secao_operacoes/extrato_missao_pdf.html', {
        'missoes': missoes,
        'data_exibicao': data_exibicao,
    }, request=request)
    pdf = HTML(string=html_string, base_url=request.build_absolute_uri('/')).write_pdf()
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="Extrato_Missoes_{data_str}.pdf"'
    return response


@sop_required
def militar_conflitos_json(request):
    """Retorna conflitos de escala/missão para um militar em uma data."""
    import datetime as dt
    militar_id = request.GET.get('militar_id')
    data_str   = request.GET.get('data', '')
    missao_id  = request.GET.get('missao_id')  # missão sendo editada (excluir da checagem)

    if not militar_id or not data_str:
        return JsonResponse({'conflitos': []})

    try:
        militar = Efetivo.objects.get(pk=militar_id, deleted=False)
        data    = dt.datetime.strptime(data_str, '%Y-%m-%d').date()
    except (Efetivo.DoesNotExist, ValueError):
        return JsonResponse({'conflitos': []})

    conflitos = []

    # 1. Situação do militar
    if militar.situacao and militar.situacao.strip():
        sit = militar.situacao.strip().upper()
        situacoes_indisp = {'BAIXADO', 'AFASTADO', 'LICENÇA', 'DISPENSA', 'HOSPITALIZADO', 'INATIVO'}
        for s in situacoes_indisp:
            if s in sit:
                conflitos.append({
                    'tipo': 'situacao',
                    'descricao': f'Situação atual: {militar.situacao}',
                })
                break

    # 2. Turnos de escala no mesmo dia
    turnos = TurnoEscala.objects.filter(militar=militar, data=data).select_related('escala', 'posto')
    for t in turnos:
        posto_str = f' — {t.posto.nome}' if t.posto else ''
        conflitos.append({
            'tipo': 'escala',
            'descricao': f'Escalado: {t.escala.nome}{posto_str} ({data.strftime("%d/%m/%Y")})',
        })

    # 3. Outras missões no mesmo dia
    missoes_qs = Missao.objects.filter(data_missao=data)
    if missao_id:
        try:
            missoes_qs = missoes_qs.exclude(pk=int(missao_id))
        except (ValueError, TypeError):
            pass

    from django.db.models import Q as Qm
    missoes_conf = missoes_qs.filter(
        Qm(equipe=militar) | Qm(cmt_missao=militar) | Qm(motorista=militar)
    ).distinct()
    for m in missoes_conf:
        papel = 'equipe'
        if m.cmt_missao == militar:
            papel = 'CMT'
        elif m.motorista == militar:
            papel = 'MOT'
        conflitos.append({
            'tipo': 'missao',
            'descricao': f'Já na OMIS Nº {m.numero} — {m.nome_missao} ({data.strftime("%d/%m/%Y")}) como {papel}',
        })

    return JsonResponse({'conflitos': conflitos, 'militar': f'{militar.posto} {militar.nome_guerra}'.strip()})


@sop_required
def efetivo_busca_json(request):
    q = request.GET.get('q', '').strip()
    qs = Efetivo.objects.filter(deleted=False).order_by('posto', 'nome_guerra')
    if q:
        qs = qs.filter(nome_guerra__icontains=q) | qs.filter(nome_completo__icontains=q) | qs.filter(posto__icontains=q)
    return JsonResponse([{
        'id': e.pk, 'posto': e.posto, 'nome_guerra': e.nome_guerra,
        'label': f"{e.posto} {e.nome_guerra}".strip(), 'oficial': e.oficial,
    } for e in qs[:30]], safe=False)


@sop_required
def missao_busca_json(request):
    q = request.GET.get('q', '').strip()
    if len(q) < 1:
        return JsonResponse([], safe=False)
    todos_anos = request.GET.get('todos_anos', '0') == '1'
    if todos_anos:
        base_qs = Missao.objects.all()
    else:
        try:
            _ano_busca = int(request.GET.get('ano', date.today().year))
        except (ValueError, TypeError):
            _ano_busca = date.today().year
        base_qs = Missao.objects.filter(data_missao__year=_ano_busca)
    try:
        num = int(q)
        missoes = base_qs.filter(Q(numero=num) | Q(nome_missao__icontains=q)).order_by('-data_missao')[:10]
    except ValueError:
        missoes = base_qs.filter(nome_missao__icontains=q).order_by('-data_missao')[:10]
    resultado = []
    for m in missoes:
        resultado.append({
            'id': m.pk,
            'label': f"Nº {m.numero} – {m.nome_missao}",
            'nome_missao': m.nome_missao,
            'local': m.local,
            'acionador': m.acionador,
            'objetivo': m.objetivo,
            'endereco': m.endereco,
            'horario_chamada': m.horario_chamada.strftime('%H:%M') if m.horario_chamada else '',
            'horario_armamento': m.horario_armamento.strftime('%H:%M') if m.horario_armamento else '',
            'horario_alimentacao': m.horario_alimentacao.strftime('%H:%M') if m.horario_alimentacao else '',
            'horario_sala_sgt': m.horario_sala_sgt.strftime('%H:%M') if m.horario_sala_sgt else '',
            'horario_saida': m.horario_saida.strftime('%H:%M') if m.horario_saida else '',
            'horario_pronto': m.horario_pronto.strftime('%H:%M') if m.horario_pronto else '',
            'transporte': m.transporte,
            'radio_nome': m.radio_nome,
            'radio_qtd': m.radio_qtd,
            'radio_canal': m.radio_canal,
            'uniforme': m.uniforme,
            'observacoes_armamento': m.observacoes_armamento,
            'cmt_a_cargo': m.cmt_a_cargo,
            'mot_a_cargo': m.mot_a_cargo,
            'equipe_a_cargo': m.equipe_a_cargo,
            'efetivo_of': m.efetivo_of,
            'efetivo_so_sgt': m.efetivo_so_sgt,
            'efetivo_cb': m.efetivo_cb,
            'efetivo_s1': m.efetivo_s1,
            'efetivo_s2': m.efetivo_s2,
            'efetivo_rec': m.efetivo_rec,
            'grupos_efetivo': json.loads(m.efetivo_grupos_json) if m.efetivo_grupos_json else _build_grupos_from_old_fields(m),
            'armamentos': [{'arma': a.arma, 'quantidade': a.quantidade, 'carregadores': a.carregadores, 'cartuchos': a.cartuchos} for a in m.armamentos.all()],
            'equipamentos': [{'equipamento': e.equipamento, 'quantidade': e.quantidade} for e in m.equipamentos.all()],
        })
    return JsonResponse(resultado, safe=False)


@sop_required
def equipamento_catalogo_json(request):
    q = request.GET.get('q', '').strip()
    qs = EquipamentoCatalogo.objects.all()
    if q:
        qs = qs.filter(nome__icontains=q)
    return JsonResponse([{'id': e.pk, 'nome': e.nome} for e in qs], safe=False)


@sop_required
def equipamento_catalogo_add(request):
    if request.method == 'POST':
        import json
        data = json.loads(request.body)
        nome = data.get('nome', '').strip().upper()
        if nome:
            obj, created = EquipamentoCatalogo.objects.get_or_create(nome=nome)
            return JsonResponse({'id': obj.pk, 'nome': obj.nome, 'created': created})
    return JsonResponse({'error': 'invalid'}, status=400)


@sop_required
def equipamento_catalogo_delete(request, pk):
    if request.method == 'POST':
        EquipamentoCatalogo.objects.filter(pk=pk).delete()
        return JsonResponse({'ok': True})
    return JsonResponse({'error': 'invalid'}, status=400)


@sop_required
def equipamento_catalogo_list(request):
    itens = EquipamentoCatalogo.objects.all()
    return render(request, 'Secao_operacoes/equipamento_catalogo.html', {'itens': itens})


def _catalogo_views(Model, add_fields_fn, list_template):
    pass  # helper não usado diretamente


def _make_catalogo_json(Model, extra_fields=None):
    @sop_required
    def view(request):
        q = request.GET.get('q', '').strip()
        qs = Model.objects.all()
        if q:
            qs = qs.filter(nome__icontains=q)
        result = []
        for obj in qs:
            d = {'id': obj.pk, 'nome': obj.nome}
            if extra_fields:
                for f in extra_fields:
                    d[f] = getattr(obj, f, '')
            result.append(d)
        return JsonResponse(result, safe=False)
    return view


def _make_catalogo_add(Model, extra_fields=None):
    @sop_required
    def view(request):
        if request.method == 'POST':
            import json
            data = json.loads(request.body)
            nome = data.get('nome', '').strip().upper()
            if not nome:
                return JsonResponse({'error': 'nome vazio'}, status=400)
            defaults = {}
            if extra_fields:
                for f in extra_fields:
                    val = data.get(f, '')
                    if val != '':
                        defaults[f] = val
            obj, created = Model.objects.get_or_create(nome=nome, defaults=defaults)
            if not created and defaults:
                for f, v in defaults.items():
                    setattr(obj, f, v)
                obj.save()
            d = {'id': obj.pk, 'nome': obj.nome, 'created': created}
            if extra_fields:
                for f in extra_fields:
                    d[f] = getattr(obj, f, '')
            return JsonResponse(d)
        return JsonResponse({'error': 'invalid'}, status=400)
    return view


def _make_catalogo_delete(Model):
    @sop_required
    def view(request, pk):
        if request.method == 'POST':
            Model.objects.filter(pk=pk).delete()
            return JsonResponse({'ok': True})
        return JsonResponse({'error': 'invalid'}, status=400)
    return view


# ── Rádio catálogo ──
radio_catalogo_json = _make_catalogo_json(RadioCatalogo, extra_fields=['canal_padrao'])
radio_catalogo_add = _make_catalogo_add(RadioCatalogo, extra_fields=['canal_padrao'])
radio_catalogo_delete = _make_catalogo_delete(RadioCatalogo)


@sop_required
def radio_catalogo_list(request):
    return render(request, 'Secao_operacoes/radio_catalogo.html', {'itens': RadioCatalogo.objects.all()})


# ── Uniforme catálogo ──
uniforme_catalogo_json = _make_catalogo_json(UniformeCatalogo)
uniforme_catalogo_add = _make_catalogo_add(UniformeCatalogo)
uniforme_catalogo_delete = _make_catalogo_delete(UniformeCatalogo)


@sop_required
def uniforme_catalogo_list(request):
    return render(request, 'Secao_operacoes/uniforme_catalogo.html', {'itens': UniformeCatalogo.objects.all()})


# ── Armamento catálogo ──
armamento_catalogo_json = _make_catalogo_json(ArmamentoCatalogo, extra_fields=['carregadores_por_unidade', 'cartuchos_por_unidade'])
armamento_catalogo_add = _make_catalogo_add(ArmamentoCatalogo, extra_fields=['carregadores_por_unidade', 'cartuchos_por_unidade'])
armamento_catalogo_delete = _make_catalogo_delete(ArmamentoCatalogo)


@sop_required
def armamento_catalogo_list(request):
    return render(request, 'Secao_operacoes/armamento_catalogo.html', {'itens': ArmamentoCatalogo.objects.all()})


def _efetivo_json_ctx():
    import json
    qs = Efetivo.objects.filter(deleted=False).order_by('posto', 'nome_guerra')
    return json.dumps([{
        'id': e.pk, 'posto': e.posto, 'nome_guerra': e.nome_guerra,
        'label': f"{e.posto} {e.nome_guerra}".strip(), 'oficial': e.oficial,
    } for e in qs])


def _build_grupos_from_old_fields(missao):
    """Constrói lista de grupos a partir dos campos antigos de missão (backward compat)."""
    grupos = []
    cmt_membros = [{'efetivo_id': missao.cmt_missao.pk, 'texto': ''}] if missao.cmt_missao else []
    cmt = {'label': 'CMT', 'membros': cmt_membros}
    if missao.cmt_a_cargo:
        cmt['acargo'] = missao.cmt_a_cargo
    grupos.append(cmt)

    mot_membros = [{'efetivo_id': missao.motorista.pk, 'texto': ''}] if missao.motorista else []
    mot = {'label': 'MOT', 'membros': mot_membros}
    if missao.mot_a_cargo:
        mot['acargo'] = missao.mot_a_cargo
    grupos.append(mot)

    eq_membros = [{'efetivo_id': e.pk, 'texto': ''} for e in missao.equipe.all().order_by('posto', 'nome_guerra')]
    equipe = {'label': 'EQUIPE', 'membros': eq_membros}
    if missao.equipe_a_cargo:
        equipe['acargo'] = missao.equipe_a_cargo
    grupos.append(equipe)
    return grupos


def _salvar_efetivo_post(request, missao):
    missao.efetivo_of     = int(request.POST.get('efetivo_of', 0) or 0)
    missao.efetivo_so_sgt = int(request.POST.get('efetivo_so_sgt', 0) or 0)
    missao.efetivo_cb     = int(request.POST.get('efetivo_cb', 0) or 0)
    missao.efetivo_s1     = int(request.POST.get('efetivo_s1', 0) or 0)
    missao.efetivo_s2     = int(request.POST.get('efetivo_s2', 0) or 0)
    missao.efetivo_rec    = int(request.POST.get('efetivo_rec', 0) or 0)

    # Novo sistema: grupos dinâmicos via JSON
    grupos_raw = request.POST.get('grupos_efetivo_json', '').strip()
    if grupos_raw:
        try:
            grupos = json.loads(grupos_raw)
        except (json.JSONDecodeError, ValueError):
            grupos = []
        missao.efetivo_grupos_json = grupos_raw

        # Backward compat: atualiza campos antigos a partir dos grupos
        cmt_grupo  = next((g for g in grupos if g.get('label', '').upper() == 'CMT'), None)
        mot_grupo  = next((g for g in grupos if g.get('label', '').upper() == 'MOT'), None)
        eq_grupo   = next((g for g in grupos if g.get('label', '').upper() == 'EQUIPE'), None)
        missao.cmt_a_cargo    = cmt_grupo.get('acargo', '')  if cmt_grupo  else ''
        missao.mot_a_cargo    = mot_grupo.get('acargo', '')  if mot_grupo  else ''
        missao.equipe_a_cargo = eq_grupo.get('acargo', '')   if eq_grupo   else ''
        cmt_id = next((m['efetivo_id'] for g in grupos if g.get('label', '').upper() == 'CMT' for m in g.get('membros', []) if m.get('efetivo_id')), None)
        mot_id = next((m['efetivo_id'] for g in grupos if g.get('label', '').upper() == 'MOT' for m in g.get('membros', []) if m.get('efetivo_id')), None)
        missao.cmt_missao = Efetivo.objects.filter(pk=cmt_id).first() if cmt_id else None
        missao.motorista  = Efetivo.objects.filter(pk=mot_id).first() if mot_id else None
    else:
        # Fallback para o sistema antigo
        missao.cmt_a_cargo    = request.POST.get('cmt_a_cargo', '').strip()
        missao.mot_a_cargo    = request.POST.get('mot_a_cargo', '').strip()
        missao.equipe_a_cargo = request.POST.get('equipe_a_cargo', '').strip()
        cmt_id = request.POST.get('cmt_missao_id')
        missao.cmt_missao = Efetivo.objects.filter(pk=cmt_id).first() if cmt_id else None
        mot_id = request.POST.get('motorista_id')
        missao.motorista = Efetivo.objects.filter(pk=mot_id).first() if mot_id else None


def _salvar_equipe_post(request, missao):
    grupos_raw = request.POST.get('grupos_efetivo_json', '').strip()
    if grupos_raw:
        try:
            grupos = json.loads(grupos_raw)
        except (json.JSONDecodeError, ValueError):
            grupos = []
        # Todos os efetivo_ids de todos os grupos
        todos_ids = [m['efetivo_id'] for g in grupos for m in g.get('membros', []) if m.get('efetivo_id')]
        missao.equipe.set(Efetivo.objects.filter(pk__in=todos_ids))
    else:
        ids = request.POST.getlist('equipe_ids[]')
        missao.equipe.set(Efetivo.objects.filter(pk__in=ids))


def _salvar_horarios(request, missao):
    item_keys = request.POST.getlist('horario_item_key[]')
    extra_labels = request.POST.getlist('horario_extra_label[]')
    extra_horas  = request.POST.getlist('horario_extra_hora[]')

    # Build config for PDF ordering
    config = []
    extra_idx = 0
    for key in item_keys:
        if key and key in _STD_MAP:
            config.append({'tipo': 'padrao', 'key': key})
        else:
            config.append({'tipo': 'extra'})

    # Save extra schedule items
    missao.horarios_extras.all().delete()
    extra_ordem = 0
    for i, label in enumerate(extra_labels):
        if label.strip():
            h = extra_horas[i].strip() if i < len(extra_horas) else ''
            ItemHorario.objects.create(
                missao=missao, label=label.strip(),
                horario=h if h else None, ordem=extra_ordem,
            )
            extra_ordem += 1

    missao.horarios_config = json.dumps(config)
    missao.save(update_fields=['horarios_config'])


def _salvar_armamentos_equipamentos(request, missao):
    armas = request.POST.getlist('arma[]')
    qtd_armas = request.POST.getlist('qtd_arma[]')
    carregadores = request.POST.getlist('carregadores[]')
    cartuchos = request.POST.getlist('cartuchos[]')
    for i, arma in enumerate(armas):
        if arma.strip():
            ItemArmamento.objects.create(
                missao=missao,
                arma=arma.strip(),
                quantidade=int(qtd_armas[i] or 0),
                carregadores=int(carregadores[i] or 0),
                cartuchos=int(cartuchos[i] or 0),
            )
    equips = request.POST.getlist('equipamento[]')
    qtd_equips = request.POST.getlist('qtd_equip[]')
    for i, eq in enumerate(equips):
        if eq.strip():
            ItemEquipamento.objects.create(
                missao=missao,
                equipamento=eq.strip(),
                quantidade=int(qtd_equips[i] or 0),
            )


# ── Configuração de Operações (apenas admin) ──────────────────────────────────

@login_required
def config_operacoes(request):
    from informatica.views import is_informatica_admin
    if not is_informatica_admin(request.user):
        messages.error(request, 'Acesso restrito ao administrador.')
        return redirect('Secao_operacoes:index')
    config = ConfiguracaoOperacoes.get_instance()
    efetivos = Efetivo.objects.filter(deleted=False).order_by('nome_guerra')
    if request.method == 'POST':
        config.observacoes_armamento_padrao = request.POST.get('observacoes_armamento_padrao', '').strip()
        # salvar diretrizes padrão como JSON
        textos_padrao = [t.strip() for t in request.POST.getlist('diretriz_padrao_texto[]') if t.strip()]
        config.diretrizes_padrao_json = json.dumps(textos_padrao, ensure_ascii=False)
        config.save()
        messages.success(request, 'Configurações salvas com sucesso.')
        return redirect('Secao_operacoes:config_operacoes')
    diretrizes_padrao = _get_diretrizes_padrao(config)
    return render(request, 'Secao_operacoes/config_operacoes.html', {
        'config': config,
        'efetivos': efetivos,
        'is_admin': request.user.is_superuser,
        'diretrizes_padrao': diretrizes_padrao,
        'diretrizes_padrao_json': json.dumps(diretrizes_padrao, ensure_ascii=False),
        'acarga_opcoes': ACargaOpcao.objects.all(),
        'acarga_opcoes_json': json.dumps(list(ACargaOpcao.objects.values('id', 'nome')), ensure_ascii=False),
    })


# ── A Cargo — opções pré-cadastradas ──────────────────────────────────────────

@login_required
def api_acarga_opcoes(request):
    from .models import ACargaOpcao
    if request.method == 'POST':
        import json as _json
        data = _json.loads(request.body)
        nome = data.get('nome', '').strip()
        if not nome:
            return JsonResponse({'status': 'error', 'message': 'Nome não pode ser vazio.'}, status=400)
        obj, created = ACargaOpcao.objects.get_or_create(nome=nome)
        return JsonResponse({'status': 'ok', 'id': obj.pk, 'nome': obj.nome, 'created': created})
    opcoes = list(ACargaOpcao.objects.values('id', 'nome'))
    return JsonResponse(opcoes, safe=False)


@login_required
def api_acarga_opcao_delete(request, pk):
    from .models import ACargaOpcao
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)
    ACargaOpcao.objects.filter(pk=pk).delete()
    return JsonResponse({'status': 'ok'})


@method_decorator(login_required, name='dispatch')
class RelsisamView(TemplateView):
    template_name = 'Secao_operacoes/relsisam.html'

    def get_context_data(self, **kwargs):
        from ESI.models import EscalaMissaoESI
        ctx = super().get_context_data(**kwargs)
        hoje = date.today()

        # De missão — SOP (OMIS)
        missoes_hoje = Missao.objects.filter(data_missao=hoje)
        de_missao_ids = set()
        for m in missoes_hoje.prefetch_related('equipe'):
            de_missao_ids.update(m.equipe.values_list('id', flat=True))
            if m.cmt_missao_id:
                de_missao_ids.add(m.cmt_missao_id)
            if m.motorista_id:
                de_missao_ids.add(m.motorista_id)

        # De missão — ESI
        de_missao_ids.update(
            EscalaMissaoESI.objects.filter(missao__data_missao=hoje)
            .values_list('militares__id', flat=True)
        )
        de_missao_ids.discard(None)

        # De serviço — TurnoEscala
        de_servico_ids = set(
            TurnoEscala.objects.filter(data=hoje).values_list('militar_id', flat=True)
        )

        # Situações especiais ativas hoje
        situacoes_qs = SituacaoEspecialEfetivo.objects.filter(
            data_inicio__lte=hoje
        ).filter(
            models.Q(data_fim__gte=hoje) | models.Q(data_fim__isnull=True)
        )
        especial_map = {s.efetivo_id: s.tipo for s in situacoes_qs}

        # Agrupar efetivos ativos por setor
        efetivos = (
            Efetivo.objects
            .filter(situacao='Ativo')
            .values('id', 'setor', 'posto', 'nome_guerra')
            .order_by('setor', 'posto', 'nome_guerra')
        )

        setores = {}
        for ef in efetivos:
            s = ef['setor'] or 'Sem setor'
            if s not in setores:
                setores[s] = {
                    'nome': s, 'total': 0,
                    'de_missao': [], 'de_servico': [],
                    'licenca': [], 'afastamento': [], 'tdo': [], 'outro': [],
                    'livre': [],
                }
            eid = ef['id']
            entrada = {'posto': ef['posto'], 'nome_guerra': ef['nome_guerra']}
            if eid in de_missao_ids:
                setores[s]['de_missao'].append(entrada)
            elif eid in de_servico_ids:
                setores[s]['de_servico'].append(entrada)
            elif eid in especial_map:
                setores[s][especial_map[eid]].append(entrada)
            else:
                setores[s]['livre'].append(entrada)
            setores[s]['total'] += 1

        ctx['setores'] = sorted(setores.values(), key=lambda x: x['nome'])
        ctx['hoje'] = hoje
        ctx['total_efetivo'] = sum(s['total'] for s in setores.values())
        ctx['total_missao'] = len(de_missao_ids)
        ctx['total_servico'] = len(de_servico_ids)
        ctx['total_especial'] = len(especial_map)
        ctx['missoes_hoje'] = missoes_hoje.count()
        return ctx


@login_required
def situacao_especial_list(request):

    hoje = date.today()
    ativas = SituacaoEspecialEfetivo.objects.filter(
        models.Q(data_fim__gte=hoje) | models.Q(data_fim__isnull=True)
    ).select_related('efetivo', 'registrado_por').order_by('tipo', 'data_inicio')
    encerradas = SituacaoEspecialEfetivo.objects.filter(
        data_fim__lt=hoje
    ).select_related('efetivo').order_by('-data_fim')[:30]
    return render(request, 'Secao_operacoes/situacao_especial_list.html', {
        'ativas': ativas,
        'encerradas': encerradas,
        'hoje': hoje,
    })


@login_required
def situacao_especial_create(request):

    TIPO_CHOICES = SituacaoEspecialEfetivo.TIPO_CHOICES
    if request.method == 'POST':
        efetivo_id = request.POST.get('efetivo_id')
        tipo = request.POST.get('tipo')
        data_inicio = request.POST.get('data_inicio')
        data_fim = request.POST.get('data_fim') or None
        observacao = request.POST.get('observacao', '')
        if efetivo_id and tipo and data_inicio:
            SituacaoEspecialEfetivo.objects.create(
                efetivo_id=efetivo_id,
                tipo=tipo,
                data_inicio=data_inicio,
                data_fim=data_fim,
                observacao=observacao,
                registrado_por=request.user,
            )
            messages.success(request, 'Situação registrada com sucesso.')
            return redirect('Secao_operacoes:situacao_especial_list')
        messages.error(request, 'Preencha todos os campos obrigatórios.')
    return render(request, 'Secao_operacoes/situacao_especial_form.html', {
        'tipo_choices': TIPO_CHOICES,
        'hoje': date.today(),
    })


@login_required
def situacao_especial_encerrar(request, pk):

    sit = get_object_or_404(SituacaoEspecialEfetivo, pk=pk)
    if request.method == 'POST':
        sit.data_fim = date.today()
        sit.save(update_fields=['data_fim'])
        messages.success(request, f'Situação de {sit.efetivo} encerrada.')
    return redirect('Secao_operacoes:situacao_especial_list')


@login_required
def situacao_especial_delete(request, pk):

    sit = get_object_or_404(SituacaoEspecialEfetivo, pk=pk)
    if request.method == 'POST':
        sit.delete()
        messages.success(request, 'Registro excluído.')
    return redirect('Secao_operacoes:situacao_especial_list')
