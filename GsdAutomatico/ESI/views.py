from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.utils import timezone

from Secao_operacoes.models import Missao
from Secao_pessoal.models import Efetivo
from .models import EscalaMissaoESI


def is_esi(user):
    return user.is_superuser or user.groups.filter(name='ESI').exists()


def esi_required(view_func):
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not is_esi(request.user):
            return render(request, 'ESI/acesso_negado.html', status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped


@esi_required
def dashboard(request):
    hoje = timezone.localdate()
    proximas = Missao.objects.filter(
        data_missao__gte=hoje
    ).select_related('cmt_missao').order_by('data_missao', 'numero')[:5]

    from django.db.models import Q as _Q
    missoes_esi = Missao.objects.filter(
        _Q(cmt_a_cargo__icontains='ESI') |
        _Q(mot_a_cargo__icontains='ESI') |
        _Q(equipe_a_cargo__icontains='ESI')
    )
    total_missoes = missoes_esi.count()
    com_escala = EscalaMissaoESI.objects.filter(missao__in=missoes_esi).count()

    sem_escala = total_missoes - com_escala

    return render(request, 'ESI/dashboard.html', {
        'proximas': proximas,
        'total_missoes': total_missoes,
        'com_escala': com_escala,
        'sem_escala': sem_escala,
        'hoje': hoje,
    })


@esi_required
def painel_missoes(request):
    from django.db.models import Q
    hoje = timezone.localdate()

    filtro = request.GET.get('filtro', 'proximas')
    busca = request.GET.get('q', '').strip()

    from django.db.models import Q as _Q
    missoes = Missao.objects.filter(
        _Q(cmt_a_cargo__icontains='ESI') |
        _Q(mot_a_cargo__icontains='ESI') |
        _Q(equipe_a_cargo__icontains='ESI')
    ).select_related('cmt_missao').prefetch_related('escala_esi__militares')

    if filtro == 'proximas':
        missoes = missoes.filter(data_missao__gte=hoje)
    elif filtro == 'passadas':
        missoes = missoes.filter(data_missao__lt=hoje)
    elif filtro == 'sem_escala':
        ids_com_escala = EscalaMissaoESI.objects.values_list('missao_id', flat=True)
        missoes = missoes.exclude(id__in=ids_com_escala)

    if busca:
        missoes = missoes.filter(
            Q(nome_missao__icontains=busca) |
            Q(numero__icontains=busca) |
            Q(local__icontains=busca)
        )

    missoes = missoes.order_by('data_missao', 'numero')

    return render(request, 'ESI/painel_missoes.html', {
        'missoes': missoes,
        'filtro': filtro,
        'busca': busca,
        'hoje': hoje,
    })


@esi_required
def missao_escala(request, missao_id):
    missao = get_object_or_404(Missao, pk=missao_id)
    escala, _ = EscalaMissaoESI.objects.get_or_create(missao=missao)

    efetivo_esi = Efetivo.objects.filter(
        setor__icontains='ESI'
    ).order_by('posto', 'nome_guerra')

    # Fallback: se ninguém no setor ESI, carrega todo efetivo ativo
    if not efetivo_esi.exists():
        efetivo_esi = Efetivo.objects.filter(ativo=True).order_by('posto', 'nome_guerra')

    return render(request, 'ESI/missao_escala.html', {
        'missao': missao,
        'escala': escala,
        'efetivo_esi': efetivo_esi,
        'militares_escalados_ids': list(escala.militares.values_list('id', flat=True)),
    })


@esi_required
@require_POST
def salvar_escala(request, missao_id):
    missao = get_object_or_404(Missao, pk=missao_id)
    escala, _ = EscalaMissaoESI.objects.get_or_create(missao=missao)

    militares_ids = request.POST.getlist('militares')
    observacoes = request.POST.get('observacoes', '')
    identificacao_pelotao = request.POST.get('identificacao_pelotao', '')

    escala.militares.set(militares_ids)
    escala.observacoes = observacoes
    escala.identificacao_pelotao = identificacao_pelotao
    escala.save()

    return redirect('ESI:missao_escala', missao_id=missao_id)


def _build_paginas(militares):
    import math
    POR_COLUNA = 10
    MAX_POR_PAGINA = 40  # máximo de militares por folha
    MIN_SEGUNDA_PAGINA = 10  # mínimo na segunda folha para redistribuição

    total = len(militares)

    # Definir cortes entre páginas
    cortes = []
    if total == 0:
        cortes = [0]
    elif total <= MAX_POR_PAGINA:
        cortes = [total]
    elif total < MAX_POR_PAGINA + MIN_SEGUNDA_PAGINA:
        # 41-49: redistribuir para segunda página ter MIN_SEGUNDA_PAGINA
        p1 = total - MIN_SEGUNDA_PAGINA
        cortes = [p1, total]
    else:
        pos = 0
        while pos < total:
            cortes.append(min(pos + MAX_POR_PAGINA, total))
            pos += MAX_POR_PAGINA

    paginas = []
    inicio = 0
    for numero, fim in enumerate(cortes, start=1):
        grupo = militares[inicio:fim]
        inicio = fim
        n = len(grupo)
        num_colunas = max(1, math.ceil(n / POR_COLUNA))
        colunas = [grupo[i * POR_COLUNA:(i + 1) * POR_COLUNA] for i in range(num_colunas)]
        linhas = []
        for row in range(POR_COLUNA):
            linha = [col[row] if row < len(col) else None for col in colunas]
            if any(x is not None for x in linha):
                linhas.append(linha)
        paginas.append({'linhas': linhas, 'num_colunas': num_colunas, 'numero': numero})

    num_paginas = len(paginas)
    return paginas, num_paginas


def _escala_pdf_ctx(missao, escala, request=None):
    import os
    from django.conf import settings
    from informatica.models import ConfiguracaoComandantes
    militares = list(escala.militares.order_by('posto', 'nome_guerra'))
    n = len(militares)

    paginas, num_paginas = _build_paginas(militares)

    config = ConfiguracaoComandantes.get_instance()
    brasao_path = os.path.join(settings.STATIC_ROOT, 'img', 'brasao.png')
    brasao_url = 'file://' + brasao_path
    return {
        'missao': missao,
        'escala': escala,
        'militares': militares,
        'paginas': paginas,
        'num_paginas': num_paginas,
        'total': n,
        'config': config,
        'brasao_url': brasao_url,
    }


@esi_required
def missao_escala_pdf(request, missao_id):
    from django.template.loader import render_to_string
    import subprocess, tempfile, os

    missao = get_object_or_404(Missao, pk=missao_id)
    escala = get_object_or_404(EscalaMissaoESI, missao=missao)

    html = render_to_string('ESI/escala_pdf.html', _escala_pdf_ctx(missao, escala, request))

    with tempfile.NamedTemporaryFile(suffix='.html', delete=False, mode='w', encoding='utf-8') as f:
        f.write(html)
        html_path = f.name

    pdf_path = html_path.replace('.html', '.pdf')
    try:
        subprocess.run(
            ['weasyprint', html_path, pdf_path],
            check=True, capture_output=True
        )
        with open(pdf_path, 'rb') as pdf_f:
            pdf_data = pdf_f.read()
    finally:
        os.unlink(html_path)
        if os.path.exists(pdf_path):
            os.unlink(pdf_path)

    response = HttpResponse(pdf_data, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="escala_esi_omis_{missao.numero}.pdf"'
    return response


@esi_required
def compilado_esi_pdf(request):
    from django.template.loader import render_to_string
    from weasyprint import HTML
    import datetime

    data_str = request.GET.get('data', '')
    try:
        data = datetime.date.fromisoformat(data_str)
    except ValueError:
        from django.http import HttpResponse
        return HttpResponse('Data inválida. Use ?data=AAAA-MM-DD', status=400)

    from django.http import HttpResponse
    escalas = EscalaMissaoESI.objects.filter(
        missao__data_missao=data,
        militares__isnull=False,
    ).distinct().select_related('missao').prefetch_related('militares').order_by('missao__numero')

    if not escalas.exists():
        return HttpResponse('Nenhuma escala ESI encontrada nesta data.', status=404)

    base_url = request.build_absolute_uri('/')
    documents = []
    for escala in escalas:
        html = render_to_string('ESI/escala_pdf.html', _escala_pdf_ctx(escala.missao, escala, request))
        doc = HTML(string=html, base_url=base_url).render()
        documents.append(doc)

    all_pages = [page for doc in documents for page in doc.pages]
    pdf = documents[0].copy(all_pages).write_pdf()

    data_fmt = data.strftime('%d-%m-%Y')
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'filename="Compilado_ESI_{data_fmt}.pdf"'
    return response


@esi_required
def api_conflitos_militar(request, missao_id, militar_id):
    """Verifica conflitos de escala/missão para um militar na data da missão."""
    missao = get_object_or_404(Missao, pk=missao_id)
    militar = get_object_or_404(Efetivo, pk=militar_id)
    data = missao.data_missao

    conflitos = []

    # Situação incompatível
    situacoes_incompativeis = ['BAIXADO', 'AFASTADO', 'LICENÇA', 'DISPENSA', 'HOSPITALIZADO', 'INATIVO']
    if militar.situacao and any(s in militar.situacao.upper() for s in situacoes_incompativeis):
        conflitos.append({'tipo': 'situacao', 'descricao': f'Situação: {militar.situacao}'})

    # Conflito de escala (serviço)
    try:
        from Secao_operacoes.models import TurnoEscala, PostoEscala
        for escala in TurnoEscala.objects.filter(data=data):
            for posto_escala in PostoEscala.objects.filter(turno=escala, efetivo=militar):
                conflitos.append({'tipo': 'escala', 'descricao': f'Escalado: {escala.nome} — {posto_escala.nome} ({data.strftime("%d/%m/%Y")})'})
    except Exception:
        pass

    # Conflito de missão
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

        # Conflito com escala ESI de outra missão
        try:
            esc_esi = m.escala_esi
            if esc_esi.militares.filter(id=militar.id).exists():
                conflitos.append({'tipo': 'missao', 'descricao': f'Já escalado no Anexo ESI da OMIS Nº {m.numero} — {m.nome_missao}'})
        except Exception:
            pass

    return JsonResponse({'conflitos': conflitos, 'militar': f'{militar.posto} {militar.nome_guerra}'})


@esi_required
def api_escala_status(request, missao_id):
    missao = get_object_or_404(Missao, pk=missao_id)
    try:
        escala = missao.escala_esi
        militares = [
            {'id': m.id, 'posto': m.posto, 'nome_guerra': m.nome_guerra}
            for m in escala.militares.order_by('posto', 'nome_guerra')
        ]
        return JsonResponse({'tem_escala': True, 'militares': militares, 'total': len(militares)})
    except EscalaMissaoESI.DoesNotExist:
        return JsonResponse({'tem_escala': False, 'militares': [], 'total': 0})
