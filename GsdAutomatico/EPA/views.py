from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Q

from Secao_operacoes.models import Missao
from Secao_pessoal.models import Efetivo
from .models import EscalaMissaoEPA
from auditoria.utils import registrar, resolver_label

_EPA_PERMISSAO_MAP = {
    'EPA - Missões': 'EPA- Missões',
}

# Filtra missões onde qualquer campo "a cargo" ou qualquer grupo do JSON menciona EPA
_EPA_Q = (
    Q(cmt_a_cargo__icontains='EPA') |
    Q(mot_a_cargo__icontains='EPA') |
    Q(equipe_a_cargo__icontains='EPA') |
    Q(efetivo_grupos_json__icontains='EPA')
)


def is_epa_missoes(user):
    return user.is_superuser or user.groups.filter(name='EPA - Missões').exists()


def epa_missoes_required(view_func):
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not is_epa_missoes(request.user):
            return render(request, 'EPA/acesso_negado.html', status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped


@epa_missoes_required
def dashboard(request):
    hoje = timezone.localdate()
    proximas = (
        Missao.objects
        .filter(_EPA_Q, data_missao__gte=hoje)
        .select_related('cmt_missao')
        .order_by('data_missao', 'numero')[:5]
    )

    missoes_epa = Missao.objects.filter(_EPA_Q)
    total_missoes = missoes_epa.count()
    com_escala = EscalaMissaoEPA.objects.filter(missao__in=missoes_epa).count()
    sem_escala = total_missoes - com_escala

    return render(request, 'EPA/dashboard.html', {
        'proximas': proximas,
        'total_missoes': total_missoes,
        'com_escala': com_escala,
        'sem_escala': sem_escala,
        'hoje': hoje,
    })


@epa_missoes_required
def painel_missoes(request):
    hoje = timezone.localdate()

    filtro = request.GET.get('filtro', 'proximas')
    busca = request.GET.get('q', '').strip()

    missoes = (
        Missao.objects
        .filter(_EPA_Q)
        .select_related('cmt_missao')
        .prefetch_related('escala_epa__militares')
    )

    if filtro == 'proximas':
        missoes = missoes.filter(data_missao__gte=hoje)
    elif filtro == 'passadas':
        missoes = missoes.filter(data_missao__lt=hoje)
    elif filtro == 'sem_escala':
        ids_com_escala = EscalaMissaoEPA.objects.values_list('missao_id', flat=True)
        missoes = missoes.exclude(id__in=ids_com_escala)

    if busca:
        missoes = missoes.filter(
            Q(nome_missao__icontains=busca) |
            Q(numero__icontains=busca) |
            Q(local__icontains=busca)
        )

    missoes = missoes.order_by('data_missao', 'numero')

    return render(request, 'EPA/painel_missoes.html', {
        'missoes': missoes,
        'filtro': filtro,
        'busca': busca,
        'hoje': hoje,
    })


@epa_missoes_required
def missao_escala(request, missao_id):
    import json as _json
    missao = get_object_or_404(Missao, pk=missao_id)
    escala, _ = EscalaMissaoEPA.objects.get_or_create(missao=missao)

    efetivo_epa = Efetivo.objects.filter(
        setor__icontains='EPA'
    ).order_by('posto', 'nome_guerra')
    if not efetivo_epa.exists():
        efetivo_epa = Efetivo.objects.filter(ativo=True).order_by('posto', 'nome_guerra')

    # Grupos da OMIS que são "A cargo do EPA"
    epa_grupos = []
    if missao.efetivo_grupos_json:
        try:
            grupos_omis = _json.loads(missao.efetivo_grupos_json)
        except (ValueError, _json.JSONDecodeError):
            grupos_omis = []
        for g in grupos_omis:
            if 'epa' in (g.get('acargo') or '').lower():
                epa_grupos.append(g.get('label', ''))

    # IDs já atribuídos por grupo (de escala.grupos_json)
    grupos_data = {}
    if escala.grupos_json:
        try:
            for g in _json.loads(escala.grupos_json):
                grupos_data[g['label']] = {
                    'militares': g.get('militares', []),
                }
        except (ValueError, _json.JSONDecodeError):
            pass

    epa_grupos_ctx = [
        {
            'label': lbl,
            'militares': grupos_data.get(lbl, {}).get('militares', []),
        }
        for lbl in epa_grupos
    ]

    return render(request, 'EPA/missao_escala.html', {
        'missao': missao,
        'escala': escala,
        'efetivo_epa': efetivo_epa,
        'militares_escalados_ids': list(escala.militares.values_list('id', flat=True)),
        'epa_grupos': epa_grupos_ctx,
        'epa_grupos_json': _json.dumps(epa_grupos_ctx, ensure_ascii=False),
        'tem_grupos': bool(epa_grupos_ctx),
    })


@epa_missoes_required
@require_POST
def salvar_escala(request, missao_id):
    missao = get_object_or_404(Missao, pk=missao_id)
    escala, _ = EscalaMissaoEPA.objects.get_or_create(missao=missao)

    import json as _json
    escala.observacoes = request.POST.get('observacoes', '')
    escala.identificacao_pelotao = request.POST.get('identificacao_pelotao', '')

    grupos_json_raw = request.POST.get('grupos_json', '').strip()
    if grupos_json_raw:
        try:
            grupos = _json.loads(grupos_json_raw)
        except (ValueError, _json.JSONDecodeError):
            grupos = []
        escala.grupos_json = grupos_json_raw
        todos_ids = [mid for g in grupos for mid in g.get('militares', [])]
        escala.save()
        escala.militares.set(todos_ids)
    else:
        militares_ids = request.POST.getlist('militares')
        todos_ids = militares_ids
        escala.grupos_json = ''
        escala.save()
        escala.militares.set(todos_ids)

    # ManyToMany .set() não dispara post_save — log explícito com lista dos escalados
    nomes_escalados = list(
        Efetivo.objects.filter(pk__in=todos_ids).values_list('nome_guerra', flat=True)
    )
    registrar(
        request.user, secao='epa',
        permissao=resolver_label(request.user, _EPA_PERMISSAO_MAP),
        acao='editou',
        descricao=f"escalou militares para OMIS {missao.numero}: {', '.join(nomes_escalados) or '(nenhum)'}",
        objeto_tipo='Escala EPA', objeto_id=missao.numero,
    )

    try:
        from notificacoes.utils import notificar
        from django.urls import reverse
        from django.contrib.auth import get_user_model
        _User = get_user_model()
        militares_nomes = ', '.join(
            m.nome_guerra for m in escala.militares.all()[:5]
        )
        usuarios_ops = _User.objects.filter(groups__name='SOP - Operações')
        if usuarios_ops.exists():
            notificar(
                usuarios_ops,
                titulo=f"EPA escalou militares para OMIS N° {missao.numero}/SOPBINFAEGL/BINFAE GL",
                corpo=f"{militares_nomes} | {missao.nome_missao} — {missao.data_missao.strftime('%d/%m/%Y')}",
                url=reverse('Secao_operacoes:missao_detail', args=[missao.pk]),
                tipo='sistema',
                origem_id=escala.pk,
                origem_tipo='EscalaMissaoEPA',
            )
    except Exception:
        pass

    return redirect('EPA:missao_escala', missao_id=missao_id)


@epa_missoes_required
def api_conflitos_militar(request, missao_id, militar_id):
    missao = get_object_or_404(Missao, pk=missao_id)
    militar = get_object_or_404(Efetivo, pk=militar_id)
    data = missao.data_missao

    conflitos = []

    situacoes_incompativeis = ['BAIXADO', 'AFASTADO', 'LICENÇA', 'DISPENSA', 'HOSPITALIZADO', 'INATIVO']
    if militar.situacao and any(s in militar.situacao.upper() for s in situacoes_incompativeis):
        conflitos.append({'tipo': 'situacao', 'descricao': f'Situação: {militar.situacao}'})

    try:
        from Secao_operacoes.models import TurnoEscala, PostoEscala
        for escala in TurnoEscala.objects.filter(data=data):
            for posto_escala in PostoEscala.objects.filter(turno=escala, efetivo=militar):
                conflitos.append({'tipo': 'escala', 'descricao': f'Escalado: {escala.nome} — {posto_escala.nome} ({data.strftime("%d/%m/%Y")})'})
    except Exception:
        pass

    from Secao_operacoes.models import Missao as MissaoOp
    for m in MissaoOp.objects.filter(data_missao=data).exclude(pk=missao_id):
        papel = None
        if m.cmt_missao_id == militar.id:
            papel = 'Cmt'
        elif m.motorista_id == militar.id:
            papel = 'Motorista'
        elif m.equipe.filter(id=militar.id).exists():
            papel = 'Equipe'
        if papel:
            conflitos.append({'tipo': 'missao', 'descricao': f'Já na OMIS Nº {m.numero} — {m.nome_missao} ({data.strftime("%d/%m/%Y")}) como {papel}'})

        try:
            esc_epa = m.escala_epa
            if esc_epa.militares.filter(id=militar.id).exists():
                conflitos.append({'tipo': 'missao', 'descricao': f'Já escalado no EPA da OMIS Nº {m.numero} — {m.nome_missao}'})
        except Exception:
            pass

        try:
            esc_esi = m.escala_esi
            if esc_esi.militares.filter(id=militar.id).exists():
                conflitos.append({'tipo': 'missao', 'descricao': f'Já escalado na ESI da OMIS Nº {m.numero} — {m.nome_missao}'})
        except Exception:
            pass

    return JsonResponse({'conflitos': conflitos, 'militar': f'{militar.posto} {militar.nome_guerra}'})


@epa_missoes_required
def api_escala_status(request, missao_id):
    missao = get_object_or_404(Missao, pk=missao_id)
    try:
        escala = missao.escala_epa
        militares = [
            {'id': m.id, 'posto': m.posto, 'nome_guerra': m.nome_guerra}
            for m in escala.militares.order_by('posto', 'nome_guerra')
        ]
        return JsonResponse({'tem_escala': True, 'militares': militares, 'total': len(militares)})
    except EscalaMissaoEPA.DoesNotExist:
        return JsonResponse({'tem_escala': False, 'militares': [], 'total': 0})
