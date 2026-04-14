from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from datetime import date
from .models import Escala, TurnoEscala, PostoEscala
from .forms import EscalaForm, TurnoEscalaForm, PostoEscalaForm
from Secao_pessoal.models import Efetivo, Notificacao


# ── Helpers ─────────────────────────────────────────────────────────────────

def _get_militar_logado(request):
    """Retorna o Efetivo vinculado ao usuário logado, ou o primeiro oficial."""
    if hasattr(request.user, 'profile') and request.user.profile.militar:
        return request.user.profile.militar
    return Efetivo.objects.filter(oficial=True).first()


def _notificar(remetente, destinatario, titulo, mensagem):
    """Cria uma Notificacao se remetente e destinatário forem válidos."""
    if remetente and destinatario:
        Notificacao.objects.create(
            remetente=remetente,
            destinatario=destinatario,
            titulo=titulo,
            mensagem=mensagem,
        )


# ── Views ────────────────────────────────────────────────────────────────────

@login_required
def index(request):
    return render(request, 'Secao_operacoes/base.html')


@login_required
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


@login_required
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


@login_required
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

            for mid in adicionados:
                try:
                    dest = Efetivo.objects.get(pk=mid)
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
                except Efetivo.DoesNotExist:
                    pass

            for mid in removidos:
                try:
                    dest = Efetivo.objects.get(pk=mid)
                    _notificar(
                        remetente=militar_logado,
                        destinatario=dest,
                        titulo=f"Remoção da Escala — {escala.nome}",
                        mensagem=(
                            f"Você foi removido da escala de serviço \"{escala.nome}\" e não faz mais parte desta equipe. "
                            f"Removido por: {militar_logado.nome_guerra if militar_logado else 'Sistema'}."
                        )
                    )
                except Efetivo.DoesNotExist:
                    pass

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


@login_required
def escala_delete(request, pk):
    escala = get_object_or_404(Escala, pk=pk)
    if request.method == 'POST':
        nome = escala.nome
        escala.delete()
        messages.success(request, f'Escala "{nome}" excluída com sucesso.')
        return redirect('Secao_operacoes:escala_list')
    return redirect('Secao_operacoes:escala_list')


@login_required
def escala_toggle_ativo(request, pk):
    escala = get_object_or_404(Escala, pk=pk)
    if request.method == 'POST':
        escala.ativo = not escala.ativo
        escala.save()
        status = "ativada" if escala.ativo else "desativada"
        messages.success(request, f'Escala "{escala.nome}" {status} com sucesso.')
    return redirect('Secao_operacoes:escala_list')


@login_required
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


@login_required
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


@login_required
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


@login_required
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


@login_required
def posto_delete(request, pk):
    posto = get_object_or_404(PostoEscala, pk=pk)
    escala_pk = posto.escala.pk
    if request.method == 'POST':
        nome = posto.nome
        posto.delete()
        messages.success(request, f'Posto "{nome}" removido.')
    return redirect('Secao_operacoes:escala_edit', pk=escala_pk)


@login_required
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
