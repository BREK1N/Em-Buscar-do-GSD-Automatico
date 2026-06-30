import re
import logging
import unicodedata

import pandas as pd
from num2words import num2words

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import PATD
from .decorators import ouvidoria_required
from Secao_pessoal.models import Efetivo

logger = logging.getLogger(__name__)

# Padrão "NNd"/"NNp" (Detenção/Prisão em N dias), em qualquer lugar do texto —
# cobre variações reais encontradas nas planilhas de 2023 a 2026, como
# "04D", "4P", "02 D", "12P(ARQUIVADO)", "8D/ ARQUIVADO ORDE- TEM BELTRANE",
# "04D BIP Nº 32 DE 23.04.2026", "DESERTOR(04P)".
PADRAO_PUNICAO = re.compile(r'(\d{1,2})\s*([DP])\b', re.IGNORECASE)


def mapear_solucao(valor):
    """Converte o valor da coluna SOLUÇÃO da planilha antiga num dicionário com os
    campos estruturados do PATD.

    - Padrão NNd/NNp (em qualquer posição do texto) => punicao 'detenção'/'prisão'
      + dias_punicao no formato lido por PATD.calcular_e_atualizar_comportamento
      (ex.: "quatro (04) dias"), entrando assim na contagem de comportamento.
    - 'REPREENSÃO...'/'RV'/'RE' => punicao 'repreensão' (sem dias).
    - Qualquer menção a 'ARQUIVAD...' (ARQUIVADO, ARQUIVADA, ARQUIVAMENTO,
      "12P(ARQUIVADO)", "ARQUIVADO POR ORDEM DO TEM X" etc.) => marca a PATD
      como arquivada (mesmo campo usado pelo arquivamento manual no sistema).
    - Qualquer menção a 'JUSTIFIC...' => marca como justificada.
    - O texto original completo é sempre preservado em 'boletim_publicacao'
      (preserva referências como "BIP Nº 32 DE 23.04.2026" e observações como
      "ARQUIVADO ORDEM TEM BELTRANE" que não cabem nos campos estruturados).
    """
    raw = (valor or '').strip()
    resultado = {
        'punicao': raw,
        'dias_punicao': '',
        'justificado': False,
        'arquivado': False,
        'motivo_arquivamento': '',
        'boletim_publicacao': raw[:100],
    }
    if not raw:
        return resultado

    upper = raw.upper()

    if upper in ('RV', 'RE') or 'REPREENS' in upper:
        resultado['punicao'] = 'repreensão'
        return resultado

    m = PADRAO_PUNICAO.search(upper)
    if m:
        dias = int(m.group(1))
        tipo = 'detenção' if m.group(2).upper() == 'D' else 'prisão'
        dias_texto = num2words(dias, lang='pt_BR')
        resultado['punicao'] = tipo
        resultado['dias_punicao'] = f"{dias_texto} ({dias:02d}) dias"

    if 'ARQUIVAD' in upper:
        resultado['arquivado'] = True
        resultado['motivo_arquivamento'] = raw

    if 'JUSTIFIC' in upper:
        resultado['justificado'] = True

    return resultado


def normalize_col(name):
    """Remove acentos/símbolos (º, °, ç, ã, etc.) para casar cabeçalhos com variações de digitação."""
    name = str(name).strip().upper()
    name = ''.join(c for c in unicodedata.normalize('NFKD', name) if not unicodedata.combining(c))
    name = re.sub(r'[^A-Z0-9 ]', ' ', name)
    return re.sub(r'\s+', ' ', name).strip()


# Cada planilha antiga (2023 a 2026) usa um nome de coluna ligeiramente
# diferente para a mesma informação (ex.: "Nº PATD" em 2025, "Nº do Processo"
# em 2023, "MOTIVO DO ARROLADO" em 2026, "SOLUÇÃ0" com zero em 2023).
# Por isso a coluna é localizada por uma palavra-chave contida no cabeçalho
# normalizado, em vez de exigir o nome exato.
COLUNAS_CHAVE = {
    'N_PATD':       ['PATD', 'PROCESSO'],
    'DATA_ABERTURA':['ABERTURA'],
    'SARAM':        ['SARAM'],
    'NOME_GUERRA':  ['NOME'],
    'SETOR':        ['SETOR'],
    'MOTIVO':       ['MOTIVO'],
    'SOLUCAO':      ['SOLU'],
    'OF_APURADOR':  ['APURADOR'],
    'TURMA':        ['TURMA'],
}
COLUNAS_OBRIGATORIAS = ['N_PATD', 'MOTIVO', 'SOLUCAO']


def localizar_colunas(colunas_normalizadas):
    mapeadas = {}
    for canonico, hints in COLUNAS_CHAVE.items():
        for col in colunas_normalizadas:
            if any(h in col for h in hints):
                mapeadas[canonico] = col
                break
    return mapeadas


@login_required
@ouvidoria_required
@require_POST
def importar_patd_legado(request):
    excel_file = request.FILES.get('excel_file')
    if not excel_file:
        messages.error(request, 'Selecione um arquivo Excel para importar.')
        return redirect('Ouvidoria:relatorio_ouvidoria')

    engine = 'pyxlsb' if excel_file.name.lower().endswith('.xlsb') else None
    try:
        df = pd.read_excel(excel_file, dtype=str, engine=engine)
    except Exception as e:
        logger.error(f"Erro ao ler Excel de histórico antigo: {e}")
        messages.error(request, f'Não foi possível ler o arquivo: {e}')
        return redirect('Ouvidoria:relatorio_ouvidoria')

    df.columns = [normalize_col(c) for c in df.columns]
    colunas = localizar_colunas(list(df.columns))

    faltando = [c for c in COLUNAS_OBRIGATORIAS if c not in colunas]
    if faltando:
        messages.error(
            request,
            'Colunas obrigatórias não encontradas na planilha: ' + ', '.join(faltando)
        )
        return redirect('Ouvidoria:relatorio_ouvidoria')

    df = df.fillna('')

    def col(row, canonico):
        c = colunas.get(canonico)
        return str(row.get(c, '')).strip() if c else ''

    criados = 0
    pulados_duplicados = 0
    sem_vinculo = 0

    for _, row in df.iterrows():
        numero_legado = col(row, 'N_PATD')
        if not numero_legado:
            continue

        saram_raw = col(row, 'SARAM')
        saram = None
        if saram_raw:
            try:
                saram = int(float(saram_raw))
            except ValueError:
                saram = None

        dup_qs = PATD.all_objects.filter(sistema_antigo=True, numero_patd_legado=numero_legado)
        if saram:
            dup_qs = dup_qs.filter(militar__saram=saram)
        if dup_qs.exists():
            pulados_duplicados += 1
            continue

        militar = Efetivo.all_objects.filter(saram=saram).first() if saram else None
        if militar is None:
            nome_guerra = col(row, 'NOME_GUERRA')
            militar = Efetivo.objects.create(
                nome_completo=nome_guerra or f'Militar SARAM {saram or "desconhecido"}',
                nome_guerra=nome_guerra,
                saram=saram,
                setor=col(row, 'SETOR'),
                deleted=True,
            )
            sem_vinculo += 1

        solucao = mapear_solucao(col(row, 'SOLUCAO'))

        data_abertura = pd.to_datetime(col(row, 'DATA_ABERTURA') or None, errors='coerce')
        data_inicio_val = data_abertura.to_pydatetime() if pd.notna(data_abertura) else timezone.now()
        data_inicio_val = timezone.make_aware(data_inicio_val) if timezone.is_naive(data_inicio_val) else data_inicio_val
        data_ocorrencia_val = data_abertura.date() if pd.notna(data_abertura) else None

        of_apurador = col(row, 'OF_APURADOR')
        turma = col(row, 'TURMA')
        observacoes = []
        if of_apurador:
            observacoes.append(f'Apurado por: {of_apurador}')
        if turma:
            observacoes.append(f'Turma: {turma}')

        patd = PATD.all_objects.create(
            militar=militar,
            transgressao=col(row, 'MOTIVO'),
            numero_patd=None,
            numero_patd_legado=numero_legado,
            sistema_antigo=True,
            data_inicio=data_inicio_val,
            data_ocorrencia=data_ocorrencia_val,
            status='finalizado',
            punicao=solucao['punicao'],
            dias_punicao=solucao['dias_punicao'],
            justificado=solucao['justificado'],
            arquivado=solucao['arquivado'],
            motivo_arquivamento=solucao['motivo_arquivamento'],
            boletim_publicacao=solucao['boletim_publicacao'],
            texto_relatorio=' | '.join(observacoes) if observacoes else '',
            deleted=False,
        )
        patd.definir_natureza_transgressao()
        patd.calcular_e_atualizar_comportamento()
        patd.save()
        criados += 1

    messages.success(
        request,
        f'{criados} PATD(s) do sistema antigo importada(s). '
        f'{pulados_duplicados} já existiam e foram ignoradas. '
        f'{sem_vinculo} sem militar cadastrado (criado registro histórico sem vínculo ativo).'
    )
    return redirect('Ouvidoria:relatorio_ouvidoria')
