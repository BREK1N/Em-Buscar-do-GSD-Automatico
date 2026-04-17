import io, os, re, logging, base64, uuid, tempfile
from uuid import uuid4
from datetime import datetime, timedelta
import locale
from dotenv import load_dotenv

from django.conf import settings
from django.utils import timezone
from django.db.models import Q
from django.core.files.base import ContentFile
from django.contrib.staticfiles.storage import staticfiles_storage
from django.contrib.staticfiles import finders
import docx
from docx import Document
from docx.shared import Cm, Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from bs4 import BeautifulSoup, NavigableString
from num2words import num2words
import fitz  # PyMuPDF

from ..models import PATD, Configuracao, Anexo
from Secao_pessoal.models import Efetivo

logger = logging.getLogger(__name__)
load_dotenv()

try:
    locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
except locale.Error:
    logger.warning("Locale pt_BR.UTF-8 não encontrado. A data pode não ser formatada corretamente.")

def get_next_patd_number():
    """
    Gera o próximo número para a PATD, procurando pelo menor número positivo vago.
    """
    numeros_usados = sorted(list(PATD.objects.filter(numero_patd__gt=0).values_list('numero_patd', flat=True)))

    if not numeros_usados:
        return 1

    numero_esperado = 1
    for numero in numeros_usados:
        if numero > numero_esperado:
            return numero_esperado
        numero_esperado = numero + 1
    
    return numeros_usados[-1] + 1


def _sync_oficial_signature(patd):
    """
    Verifica e sincroniza a assinatura do oficial responsável para a PATD.

    Esta função verifica se:
    1. A PATD tem um oficial responsável designado.
    2. O oficial já aceitou a atribuição (status não é inicial).
    3. O oficial tem uma assinatura padrão em seu perfil.
    4. A PATD ainda não tem uma assinatura de oficial específica.

    Se todas as condições forem verdadeiras, a assinatura padrão do oficial
    é copiada para a PATD. Retorna True se a assinatura foi copiada.
    """
    try:
        oficial = patd.oficial_responsavel
        is_past_acceptance = patd.status not in ['definicao_oficial', 'aguardando_aprovacao_atribuicao']
        
        if oficial and is_past_acceptance and oficial.assinatura and not patd.assinatura_oficial:
            if ';base64,' in oficial.assinatura:
                format, imgstr = oficial.assinatura.split(';base64,')
                ext = format.split('/')[-1] if '/' in format else 'png'
                file_name = f'sig_oficial_{oficial.pk}_{patd.pk}.{ext}'
                
                decoded_file = base64.b64decode(imgstr)
                file_content = ContentFile(decoded_file, name=file_name)
                
                patd.assinatura_oficial.save(file_name, file_content, save=False)
                patd.save(update_fields=['assinatura_oficial'])
                logger.info(f"Assinatura do oficial {oficial.nome_guerra} sincronizada para a PATD {patd.numero_patd}.")
                return True
            else:
                logger.warning(f"Formato de assinatura do oficial {oficial.nome_guerra} é inválido durante a sincronização.")
    except Exception as e:
        logger.error(f"Erro ao sincronizar a assinatura do oficial para a PATD {patd.pk}: {e}")
    
    return False


def format_militar_string(militar, with_spec=False):
    """
    Formata o nome do militar, colocando o nome de guerra em negrito (com **).
    Lida com casos complexos como 'D. PAULA'.
    """
    if not militar:
        return ""

    nome_completo = militar.nome_completo
    nome_guerra = militar.nome_guerra

    # Limpa o nome de guerra de pontuações e divide em partes
    guerra_parts = re.sub(r'[^\w\s]', '', nome_guerra).upper().split()

    # Divide o nome completo em palavras para manipulação
    nome_completo_words = nome_completo.split()

    # Itera sobre cada parte do nome de guerra
    for part in guerra_parts:
        if len(part) == 1:  # Se for uma inicial (ex: 'D')
            last_match_index = -1
            # Encontra o índice da ÚLTIMA palavra no nome completo que começa com essa inicial
            for i, word in enumerate(nome_completo_words):
                if word.upper().startswith(part):
                    last_match_index = i

            # Se encontrou uma correspondência, aplica o negrito apenas na inicial
            if last_match_index != -1:
                word_to_format = nome_completo_words[last_match_index]
                # Coloca em negrito apenas a primeira letra
                formatted_word = f"**{word_to_format[0]}**{word_to_format[1:]}"
                nome_completo_words[last_match_index] = formatted_word

        else:  # Se for uma palavra completa (ex: 'PAULA')
            # Procura a palavra exata no nome completo e aplica o negrito
            for i, word in enumerate(nome_completo_words):
                # Remove pontuação da palavra do nome completo para comparação
                clean_word = re.sub(r'[^\w\s]', '', word)
                if clean_word.upper() == part:
                    nome_completo_words[i] = f"**{word}**"
                    break # Para de procurar após encontrar a primeira correspondência

    formatted_name = ' '.join(nome_completo_words)
    posto = getattr(militar, 'posto', '')

    if with_spec:
        especializacao = getattr(militar, 'especializacao', '')
        return f"{posto} {especializacao} {formatted_name}".strip()
    else:
        return f"{posto} {formatted_name}".strip()


def buscar_militar_inteligente(acusado_ia):
    """
    Busca um militar dando prioridade absoluta ao SARAM,
    seguido pelo Nome de Guerra (cruzado com Posto),
    e por fim o Nome Completo.
    """
    # 1. TENTATIVA POR SARAM (Prioridade Máxima - Identificador Único)
    if acusado_ia.saram:
        # Remove pontos, traços e espaços para deixar apenas números
        saram_limpo = re.sub(r'\D', '', str(acusado_ia.saram))
        if saram_limpo:
            try:
                return Efetivo.objects.get(saram=int(saram_limpo))
            except (Efetivo.DoesNotExist, ValueError):
                pass # SARAM não encontrado ou inválido, continua para o nome...

    # Preparar filtros de texto para Posto
    filtro_posto = Q()
    if acusado_ia.posto_graduacao:
        # Mapeamento simples para normalizar postos (Ex: 'Soldado' -> 'S1' ou 'S2')
        posto_str = acusado_ia.posto_graduacao.upper()
        if 'SOLDADO' in posto_str:
            filtro_posto = Q(posto__in=['S1', 'S2'])
        elif 'CABO' in posto_str:
            filtro_posto = Q(posto='CB')
        elif 'SARGENTO' in posto_str:
            filtro_posto = Q(posto__in=['1S', '2S', '3S'])
        else:
            # Tenta busca direta (Ex: '3S', '1T', 'CAP')
            filtro_posto = Q(posto__icontains=acusado_ia.posto_graduacao)

    # 2. TENTATIVA POR NOME DE GUERRA (Sua solicitação de prioridade)
    if acusado_ia.nome_guerra:
        # Busca exata pelo nome de guerra primeiro
        candidatos = Efetivo.objects.filter(nome_guerra__iexact=acusado_ia.nome_guerra)
        
        # Se não achar exato, tenta "contém" (para casos de erro de digitação da IA)
        if not candidatos.exists():
            candidatos = Efetivo.objects.filter(nome_guerra__icontains=acusado_ia.nome_guerra)

        if candidatos.exists():
            # SE TIVER MAIS DE UM, precisamos desempatar
            if candidatos.count() > 1:
                # A) Desempate pelo Posto/Graduação (Muito Eficaz)
                if acusado_ia.posto_graduacao:
                    candidatos_posto = candidatos.filter(filtro_posto)
                    if candidatos_posto.exists():
                        if candidatos_posto.count() == 1:
                            return candidatos_posto.first()
                        candidatos = candidatos_posto # Refina a lista de candidatos

                # B) Desempate pelo Nome Completo (se disponível)
                if acusado_ia.nome_completo:
                    # Verifica se partes do nome completo da IA estão no nome completo do banco
                    palavras_nome_ia = acusado_ia.nome_completo.split()
                    for cand in candidatos:
                        match_count = sum(1 for p in palavras_nome_ia if p.lower() in cand.nome_completo.lower())
                        # Se bater 2 ou mais nomes (Ex: sobrenomes), assume que é ele
                        if match_count >= 2:
                            return cand
            
            # Se sobrou apenas 1 ou não conseguimos desempatar, retorna o primeiro encontrado
            # (Aqui atende sua regra: achou pelo nome de guerra, retorna ele)
            return candidatos.first()

    # 3. TENTATIVA POR NOME COMPLETO (Fallback)
    if acusado_ia.nome_completo:
        candidatos = Efetivo.objects.filter(nome_completo__icontains=acusado_ia.nome_completo)
        if candidatos.exists():
            if candidatos.count() > 1 and acusado_ia.posto_graduacao:
                 # Tenta desempatar pelo posto novamente
                 candidatos_filtrados = candidatos.filter(filtro_posto)
                 if candidatos_filtrados.exists():
                     return candidatos_filtrados.first()
            return candidatos.first()

    return None


def _pdf_to_pages_html(pdf_path):
    """
    Converte cada página de um PDF em uma imagem base64 e retorna HTML
    com cada página separada por um marcador de quebra de página.
    Usado para exibir o PDF fielmente no visualizador de documentos.
    """
    try:
        if not os.path.exists(pdf_path):
            return '<p style="color:red;">[Erro: arquivo PDF não encontrado]</p>'

        pdf_doc = fitz.open(pdf_path)
        parts = []
        for page_num, page in enumerate(pdf_doc):
            mat = fitz.Matrix(220 / 72, 220 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            b64 = base64.b64encode(img_bytes).decode('utf-8')
            img_html = (
                f'<img src="data:image/png;base64,{b64}" '
                f'alt="Página {page_num + 1} do ofício" '
                f'style="width:100%; height:auto; display:block;" />'
            )
            if page_num > 0:
                parts.append('<div class="manual-page-break"></div>')
            parts.append(img_html)
        pdf_doc.close()
        return ''.join(parts)
    except Exception as e:
        logger.error(f"Erro ao converter PDF para imagens HTML: {e}")
        return '<p style="color:red;">[Erro ao processar o PDF]</p>'


def _get_document_context(patd, for_docx=False):
    """
    Função centralizada para coletar e formatar todos os dados
    necessários para qualquer documento.
    """
    config = Configuracao.load()
    comandante_gsd = config.comandante_gsd
    comandante_bagl = config.comandante_bagl
    now = timezone.now()

    # Formatações de Data
    data_inicio = patd.data_inicio
    data_patd_fmt = data_inicio.strftime('%d%m%Y')
    
    if for_docx:
        # Tenta definir o local, mas tem um fallback robusto se falhar.
        try:
            locale.setlocale(locale.LC_TIME, 'pt_BR.UTF-8')
        except locale.Error:
            try:
                locale.setlocale(locale.LC_TIME, 'Portuguese_Brazil.1252')
            except locale.Error:
                logger.warning("Locales for Portuguese not found. Using manual month name conversion.")

        data_ocorrencia_fmt = patd.data_ocorrencia.strftime('%d/%m/%Y') if patd.data_ocorrencia else ""
        data_oficio_fmt = patd.data_oficio.strftime('%d/%m/%Y') if patd.data_oficio else ""

        data_ciencia_fmt = patd.data_ciencia.strftime('%d/%m/%Y') if patd.data_ciencia else ""
        data_alegacao_fmt = patd.data_alegacao.strftime('%d/%m/%Y') if patd.data_alegacao else ""
        data_publicacao_fmt = patd.data_publicacao_punicao.strftime('%d/%m/%Y') if patd.data_publicacao_punicao else ""
        data_reconsideracao_fmt = patd.data_reconsideracao.strftime('%d/%m/%Y') if patd.data_reconsideracao else ""
        dia_fmt = str(data_inicio.day)
        
        # --- INÍCIO DA MODIFICAÇÃO: Fallback manual para nomes de meses ---
        meses_em_portugues = {
            1: 'janeiro', 2: 'fevereiro', 3: 'março', 4: 'abril',
            5: 'maio', 6: 'junho', 7: 'julho', 8: 'agosto',
            9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro'
        }
        # Tenta usar o locale primeiro, se falhar, usa o dicionário
        try:
            mes_fmt = data_inicio.strftime('%B')
            # Se o resultado for em inglês, o locale falhou, então usamos o fallback
            if mes_fmt.lower() in ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december']:
                 mes_fmt = meses_em_portugues.get(data_inicio.month, '')
        except:
            mes_fmt = meses_em_portugues.get(data_inicio.month, '')
        # --- FIM DA MODIFICAÇÃO ---

        ano_fmt = str(data_inicio.year)
    else:
        data_ocorrencia_fmt = patd.data_ocorrencia.strftime('%d/%m/%Y') if patd.data_ocorrencia else "[Data não informada]"
        data_oficio_fmt = patd.data_oficio.strftime('%d/%m/%Y') if patd.data_oficio else "[Data não informada]"

        data_ciencia_fmt = f'<input type="date" class="editable-date" data-date-field="data_ciencia" value="{patd.data_ciencia.strftime("%Y-%m-%d") if patd.data_ciencia else ""}" >'
        data_alegacao_fmt = f'<input type="date" class="editable-date" data-date-field="data_alegacao" value="{patd.data_alegacao.strftime("%Y-%m-%d") if patd.data_alegacao else ""}" >'
        data_publicacao_fmt = f'<input type="date" class="editable-date" data-date-field="data_publicacao_punicao" value="{patd.data_publicacao_punicao.strftime("%Y-%m-%d") if patd.data_publicacao_punicao else ""}" >'
        data_reconsideracao_fmt = f'<input type="date" class="editable-date" data-date-field="data_reconsideracao" value="{patd.data_reconsideracao.strftime("%Y-%m-%d") if patd.data_reconsideracao else ""}" >'
        
        meses = ['Janeiro', 'Fevereiro', 'Março', 'Abril', 'Maio', 'Junho', 'Julho', 'Agosto', 'Setembro', 'Outubro', 'Novembro', 'Dezembro']
        mes_select_html = f'<select class="editable-date-part" data-date-field="data_inicio" data-date-part="month">'
        for i, nome_mes in enumerate(meses):
            selected = 'selected' if data_inicio.month == i + 1 else ''
            mes_select_html += f'<option value="{i+1}" {selected}>{nome_mes}</option>'
        mes_select_html += '</select>'
        
        dia_fmt = f'<input type="number" class="editable-date-part" data-date-field="data_inicio" data-date-part="day" value="{data_inicio.day}" min="1" max="31">'
        mes_fmt = mes_select_html
        ano_fmt = f'<input type="number" class="editable-date-part" data-date-field="data_inicio" data-date-part="year" value="{data_inicio.year}" min="2000" max="2100">'

    # Formatação de Itens Enquadrados e Circunstâncias
    itens_enquadrados_str = ", ".join([str(item.get('numero', '')) for item in patd.itens_enquadrados]) if patd.itens_enquadrados else ""
    atenuantes_str = ", ".join(patd.circunstancias.get('atenuantes', [])) if patd.circunstancias else "Nenhuma"
    agravantes_str = ", ".join(patd.circunstancias.get('agravantes', [])) if patd.circunstancias else "Nenhuma"

    # --- LÓGICA DE FORMATAÇÃO DA PUNIÇÃO ATUALIZADA ---
    # Formatação da Punição Completa
    punicao_final_str = patd.punicao or "[Punição não definida]"
    if patd.dias_punicao and patd.punicao:
        # A lógica agora constrói a string completa, ex: "Seis (06) de detenção"
        punicao_final_str = f"{patd.dias_punicao} de {patd.punicao}"

    # Cálculo do Prazo Final (Deadline) para Preclusão
    deadline_str = "[Prazo não iniciado]"
    if patd.data_ciencia:
        dias_uteis_a_adicionar = config.prazo_defesa_dias
        data_final = patd.data_ciencia
        dias_adicionados = 0
        while dias_adicionados < dias_uteis_a_adicionar:
            data_final += timedelta(days=1)
            if data_final.weekday() < 5:
                dias_adicionados += 1
        deadline = data_final + timedelta(minutes=config.prazo_defesa_minutos)
        deadline_str = deadline.strftime('%d/%m/%Y às %H:%M')

    # Lógica para Oficial Apurador
    oficial_definido = patd.status not in ['definicao_oficial', 'aguardando_aprovacao_atribuicao']

    localidade_value = patd.circunstancias.get('localidade', 'Rio de Janeiro') if patd.circunstancias else 'Rio de Janeiro'

    # Adiciona o anexo do ofício de lançamento ao contexto, se existir
    oficio_anexo = patd.anexos.filter(tipo='oficio_lancamento').first()
    oficio_lancamento_html = ''
    if oficio_anexo:
        if for_docx:
            oficio_lancamento_html = f'<embed src="{oficio_anexo.arquivo.url}" type="application/pdf" width="100%" height="800px" />'
        else:
            oficio_lancamento_html = _pdf_to_pages_html(oficio_anexo.arquivo.path)

    # Adiciona a ficha individual ao contexto, se existir
    ficha_individual_anexo = patd.anexos.filter(tipo='ficha_individual').first()
    ficha_individual_html = ''
    if ficha_individual_anexo:
        if for_docx:
            ficha_individual_html = f'<embed src="{ficha_individual_anexo.arquivo.url}" type="application/pdf" width="100%" height="800px" />'
        else:
            ficha_individual_html = _pdf_to_pages_html(ficha_individual_anexo.arquivo.path)

    context = {
        # Placeholders Comuns
        # --- CORREÇÃO: Usar staticfiles_storage.url ---
        '{Brasao da Republica}': f"<img src='{staticfiles_storage.url('img/brasao.png')}' alt='Brasão da República' style='width: 100px; height: auto;'>",
        # --- FIM DA CORREÇÃO ---
        '{N PATD}': str(patd.numero_patd),
        '{DataPatd}': data_patd_fmt,
        '{Localidade}': f'<input type="text" class="editable-text" data-text-field="localidade" value="{localidade_value}">' if not for_docx else localidade_value,
        '{dia}': dia_fmt,
        '{Mês}': mes_fmt,
        '{Ano}': ano_fmt,

        # Dados do Militar Arrolado
        '{Militar Arrolado}': format_militar_string(patd.militar),
        '{Saram Militar Arrolado}': str(getattr(patd.militar, 'saram', '[Não informado]')),
        '{Setor Militar Arrolado}': getattr(patd.militar, 'setor', '[Não informado]') ,

        # Dados do Oficial Apurador
        '{Oficial Apurador}': format_militar_string(patd.oficial_responsavel) if oficial_definido else ' ',
        '{Posto/Especialização Oficial Apurador}': format_militar_string(patd.oficial_responsavel, with_spec=True) if oficial_definido else " ",
        '{Saram Oficial Apurador}': str(getattr(patd.oficial_responsavel, 'saram', 'N/A')) if oficial_definido else " ",
        '{Setor Oficial Apurador}': getattr(patd.oficial_responsavel, 'setor', 'N/A') if oficial_definido else " ",
        '{Assinatura Oficial Apurador}': '{Assinatura_Imagem_Oficial_Apurador}' if oficial_definido and patd.oficial_responsavel and patd.oficial_responsavel.assinatura else (' ' if not oficial_definido else '{Botao Assinar Oficial}'),

        # Dados do Comandante
        '{Comandante /Posto/Especialização}': format_militar_string(comandante_gsd, with_spec=True) if comandante_gsd else "[Comandante GSD não definido]",
        '{Comandante_bagl_botao}': format_militar_string(comandante_bagl, with_spec=True) if comandante_bagl else "[Comandante BAGL não definido]",


        # Dados da Transgressão
        '{data da Ocorrencia}': data_ocorrencia_fmt,
        '{Ocorrencia reescrita}': patd.ocorrencia_reescrita or patd.transgressao,
        '{protocolo comaer}': patd.protocolo_comaer,
        '{Oficio Transgressao}': patd.oficio_transgressao,
        '{data_oficio}': data_oficio_fmt,
        '{comprovante}': patd.comprovante or '',
        '{oficio_lancamento}': oficio_lancamento_html,


        # Dados da Apuração
        '{Itens enquadrados}': itens_enquadrados_str,
        '{Atenuante}': atenuantes_str,
        '{agravantes}': agravantes_str,
        '{transgressao_afirmativa}': patd.transgressao_afirmativa or '',
        '{natureza_transgressao}': patd.natureza_transgressao or '',

        # Dados da Defesa
        '{data ciência}': data_ciencia_fmt,
        '{Data da alegação}': data_alegacao_fmt,
        '{Alegação_defesa_resumo}': patd.alegacao_defesa_resumo or '',

        # Placeholders de Punição
        '{punicao_completa}': punicao_final_str,
        '{punicao}': punicao_final_str,
        '{punição_botao}': f"{patd.nova_punicao_dias} de {patd.nova_punicao_tipo}" if patd.nova_punicao_dias else '{Botao Definir Nova Punicao}',
        '{dias_punicao}': "",
        '{comportamento}': patd.comportamento or "[Não avaliado]",
        '{data_publicacao_punicao}': data_publicacao_fmt,

        # Placeholders de Assinatura
        # --- ALTERAÇÃO: Inicialmente, o placeholder do CMD fica como texto ---
        '{Assinatura Comandante do GSD}': ' ',
        '{Assinatura Alegacao Defesa}': '{Assinatura Alegacao Defesa}' if patd.assinatura_alegacao_defesa else '{Botao Assinar Defesa}',
        '{Assinatura Reconsideracao}': '{Assinatura Reconsideracao}' if patd.assinatura_reconsideracao else '{Botao Assinar Reconsideracao}',

        # Testemunhas
        '{Testemunha 1}': format_militar_string(patd.testemunha1) if patd.testemunha1 else '[Testemunha não definida]',
        '{Testemunha 2}': format_militar_string(patd.testemunha2) if patd.testemunha2 else '[Testemunha não definida]',
        '{Assinatura Testemunha 1}': '{Assinatura_Imagem_Testemunha_1}' if patd.assinatura_testemunha1 else ('{Botao Assinar Testemunha 1}' if patd.testemunha1 else '[Sem assinatura]'),
        '{Assinatura Testemunha 2}': '{Assinatura_Imagem_Testemunha_2}' if patd.assinatura_testemunha2 else ('{Botao Assinar Testemunha 2}' if patd.testemunha2 else '[Sem assinatura]'),

        # Específicos
        '{Data Final Prazo}': deadline_str,
        '{texto_relatorio}': patd.texto_relatorio or '',
        '{Texto_reconsideracao}': patd.texto_reconsideracao or '',
        '{Data_reconsideracao}': data_reconsideracao_fmt,
        '{pagina_alegacao}': "{pagina_alegacao}", # Mantém como placeholder
        '{ficha_individual}': ficha_individual_html
    }

    # Adiciona os dados das assinaturas AO CONTEXTO APENAS SE APLICÁVEL
    # Assinatura do Oficial Apurador
    if oficial_definido and patd.oficial_responsavel and patd.oficial_responsavel.assinatura:
        context['assinatura_oficial_data'] = patd.oficial_responsavel.assinatura

    # Assinatura do Comandante - SÓ ADICIONA SE A PATD JÁ FOI APROVADA
    status_aprovados_e_posteriores = [
        'aguardando_assinatura_npd', 'periodo_reconsideracao', 'em_reconsideracao',
        'aguardando_comandante_base', 'aguardando_preenchimento_npd_reconsideracao',
        'aguardando_publicacao', 'finalizado'
    ]
    if comandante_gsd and comandante_gsd.assinatura and patd.status in status_aprovados_e_posteriores:
        context['assinatura_comandante_data'] = comandante_gsd.assinatura
        # Atualiza o placeholder no contexto para usar a imagem
        context['{Assinatura Comandante do GSD}'] = '{Assinatura_Imagem_Comandante_GSD}'

    return context


def _apply_context_to_text(text, context, template_name=''):
    """Aplica substituição de placeholders no texto e aplica regex especiais."""
    if template_name and ('RELATORIO_DELTA' in template_name or 'RELATORIO_JUSTIFICADO' in template_name):
        text = re.sub(r'(à fl\.)(\s*\d+\s*)([\,\.\s])', r'\1 {pagina_alegacao}\3', text)
    for placeholder, value in context.items():
        text = text.replace(str(placeholder), str(value))
    return text


def _get_effective(pf, sf, attr):
    """Lê atributo do paragraph_format; se None, lê do style_format (herança Word)."""
    val = getattr(pf, attr, None)
    if val is None and sf is not None:
        val = getattr(sf, attr, None)
    return val


def _apply_fmt_to_segment(text, bold, italic, underline, font_size):
    """Aplica formatação HTML a um segmento de texto simples."""
    if not text:
        return ''
    if '<' in text:
        # Já contém HTML (ex: botão de assinatura) — não envolver
        return text
    result = text
    if font_size:
        result = f'<span style="font-size: {font_size:.1f}pt">{result}</span>'
    if underline:
        result = f'<u>{result}</u>'
    if italic:
        result = f'<em>{result}</em>'
    if bold:
        result = f'<strong>{result}</strong>'
    return result


def _render_paragraph_with_placeholders(runs, context, template_name=''):
    """
    Substitui placeholders no texto completo do parágrafo preservando a formatação
    correta por segmento.

    Estratégia:
    1. Constrói mapa char→formato a partir dos runs
    2. Localiza placeholders no texto completo (p.text) — suporta placeholders
       divididos entre múltiplos runs
    3. Divide o texto em segmentos: texto-normal | placeholder | texto-normal …
    4. Cada segmento herda a formatação do primeiro caractere correspondente no DOCX
    5. Segmentos contíguos com mesma formatação são agrupados antes de emitir HTML
    """
    full_text = ''.join(r.text for r in runs)
    if not full_text:
        return ''

    # --- 1. Mapa char → (bold, italic, underline, font_size_pt) ---
    char_fmts = []
    for run in runs:
        try:
            fs = run.font.size / 12700 if run.font.size else None
        except Exception:
            fs = None
        fmt = (bool(run.bold), bool(run.italic), bool(run.underline), fs)
        for _ in run.text:
            char_fmts.append(fmt)

    # Fallback se o mapa ficar vazio
    default_fmt = (False, False, False, None)

    def fmt_at(pos):
        if 0 <= pos < len(char_fmts):
            return char_fmts[pos]
        return default_fmt

    # --- 2. Localiza todos os placeholders no full_text ---
    # Cada entrada: (start, end, substituted_value)
    placeholder_spans = []
    for ph, val in context.items():
        ph_str = str(ph)
        if not ph_str:
            continue
        search_start = 0
        while True:
            idx = full_text.find(ph_str, search_start)
            if idx == -1:
                break
            placeholder_spans.append((idx, idx + len(ph_str), str(val)))
            search_start = idx + len(ph_str)

    if not placeholder_spans:
        # Nenhum placeholder encontrado — renderiza como texto simples com fmt do 1º char
        fmt = fmt_at(0)
        return _apply_fmt_to_segment(full_text, *fmt)

    # Ordena por posição de início; remove sobreposições simples
    placeholder_spans.sort(key=lambda x: x[0])

    # --- 3. Divide em segmentos ---
    segments = []  # list of (text, bold, italic, underline, font_size)
    cursor = 0
    for start, end, val in placeholder_spans:
        if start < cursor:
            continue  # sobreposição — ignora
        # Texto antes do placeholder
        if cursor < start:
            before = full_text[cursor:start]
            fmt = fmt_at(cursor)
            segments.append((before, *fmt))
        # Valor substituído — usa formatação do primeiro char do placeholder
        fmt = fmt_at(start)
        segments.append((val, *fmt))
        cursor = end

    # Texto após o último placeholder
    if cursor < len(full_text):
        remaining = full_text[cursor:]
        fmt = fmt_at(cursor)
        segments.append((remaining, *fmt))

    # --- 4. Aplica regex especial (ex: pagina_alegacao) ---
    if template_name and ('RELATORIO_DELTA' in template_name or 'RELATORIO_JUSTIFICADO' in template_name):
        new_segments = []
        for seg_text, bold, italic, underline, fs in segments:
            seg_text = re.sub(r'(à fl\.)(\s*\d+\s*)([\,\.\s])', r'\1 {pagina_alegacao}\3', seg_text)
            new_segments.append((seg_text, bold, italic, underline, fs))
        segments = new_segments

    # --- 5. Emite HTML ---
    result = ''
    for seg_text, bold, italic, underline, fs in segments:
        result += _apply_fmt_to_segment(seg_text, bold, italic, underline, fs)
    return result


def _render_paragraph_html(p, context, template_name=''):
    """
    Converte um parágrafo python-docx em HTML preservando fielmente o DOCX:
    - Alinhamento (parágrafo ou herdado do estilo)
    - Bold, Italic, Underline e tamanho de fonte por run
    - line_spacing EXACTLY convertido para line-height em pt
    - space_before / space_after como margin
    - Indentação left e first_line
    - Margem zero por padrão (sem espaço extra do browser)
    """
    from docx.enum.text import WD_LINE_SPACING as WD_LS
    alignment_map = {None: 'left', 0: 'left', 1: 'center', 2: 'right', 3: 'justify'}

    pf = p.paragraph_format
    sf = p.style.paragraph_format if p.style else None

    # Alinhamento — parágrafo primeiro, depois estilo
    alignment = alignment_map.get(_get_effective(pf, sf, 'alignment'), 'left')

    # Base: zeramos margem para não herdar padrão do browser
    para_styles = [
        f'text-align: {alignment}',
        'margin: 0',
        'padding: 0',
    ]

    # space_before / space_after (em pt)
    try:
        sb = _get_effective(pf, sf, 'space_before')
        if sb is not None and sb.pt > 0:
            para_styles.append(f'margin-top: {sb.pt:.2f}pt')
    except Exception:
        pass
    try:
        sa = _get_effective(pf, sf, 'space_after')
        if sa is not None and sa.pt > 0:
            para_styles.append(f'margin-bottom: {sa.pt:.2f}pt')
    except Exception:
        pass

    # line_spacing — EXACTLY → line-height fixo em pt; MULTIPLE → relativo
    try:
        ls = _get_effective(pf, sf, 'line_spacing')
        ls_rule = _get_effective(pf, sf, 'line_spacing_rule')
        if ls is not None and ls_rule is not None:
            if ls_rule == WD_LS.EXACTLY:
                ls_pt = ls.pt if hasattr(ls, 'pt') else ls / 12700
                para_styles.append(f'line-height: {ls_pt:.2f}pt')
            elif ls_rule == WD_LS.AT_LEAST:
                ls_pt = ls.pt if hasattr(ls, 'pt') else ls / 12700
                para_styles.append(f'min-height: {ls_pt:.2f}pt')
            # WD_LS.MULTIPLE: ls é float (ex: 1.5) → line-height relativo
            elif isinstance(ls, (int, float)):
                para_styles.append(f'line-height: {ls}')
    except Exception:
        pass

    # Indentação left e first_line — parágrafo depois estilo
    try:
        li = _get_effective(pf, sf, 'left_indent')
        if li is not None and li.pt != 0:
            para_styles.append(f'padding-left: {li.pt:.2f}pt')
    except Exception:
        pass
    try:
        fi = _get_effective(pf, sf, 'first_line_indent')
        if fi is not None:
            para_styles.append(f'text-indent: {fi.pt:.2f}pt')
    except Exception:
        pass

    style_attr = '; '.join(para_styles)

    full_text = p.text

    # Detecta se algum placeholder do contexto aparece no texto completo.
    # Placeholders podem estar divididos entre múltiplos runs no Word — por isso
    # a substituição deve ser feita no texto completo (p.text), não por run.
    has_any_placeholder = any(str(ph) in full_text for ph, val in context.items() if ph and val)

    if has_any_placeholder or not p.runs:
        # Substitui placeholders preservando formatação por segmento
        inner_html = _render_paragraph_with_placeholders(p.runs, context, template_name)
        if not inner_html and not p.runs:
            # Parágrafo sem runs — substitui no texto simples sem formatação
            inner_html = _apply_context_to_text(full_text, context, template_name)
    else:
        # Sem placeholder: processa run a run para preservar formatação precisa
        inner_html = _render_runs_html(p.runs, context, template_name)

    return f'<p style="{style_attr}">{inner_html}</p>'


def _render_runs_html(runs, context, template_name=''):
    """Converte runs de um parágrafo em HTML com formatação por run."""
    result = ''
    for run in runs:
        text = _apply_context_to_text(run.text, context, template_name)
        if not text:
            continue

        # Estilo do run
        run_styles = []
        try:
            if run.font.size:
                pt = run.font.size / 12700  # EMU → pt
                run_styles.append(f'font-size: {pt:.1f}pt')
        except Exception:
            pass
        try:
            if run.font.color and run.font.color.type is not None:
                rgb = run.font.color.rgb
                run_styles.append(f'color: #{str(rgb)}')
        except Exception:
            pass

        # Formatação inline
        bold = run.bold
        italic = run.italic
        underline = run.underline

        if run_styles:
            text = f'<span style="{"; ".join(run_styles)}">{text}</span>'
        if underline:
            text = f'<u>{text}</u>'
        if italic:
            text = f'<em>{text}</em>'
        if bold:
            text = f'<strong>{text}</strong>'

        result += text
    return result


def _render_table_html(table, context, template_name=''):
    """Converte uma tabela python-docx em HTML."""
    html = '<table class="doc-table" style="width:100%; border-collapse:collapse; margin: 4pt 0;">'
    for row in table.rows:
        html += '<tr>'
        for cell in row.cells:
            cell_inner = ''
            for p in cell.paragraphs:
                cell_inner += _render_paragraph_html(p, context, template_name)
            # Borda e padding mínimos para manter fidelidade visual
            html += f'<td style="border: 1px solid #ccc; padding: 4pt 6pt; vertical-align: top;">{cell_inner}</td>'
        html += '</tr>'
    html += '</table>'
    return html


def _render_document_from_template(template_name, context):
    """
    Função genérica para renderizar um documento .docx a partir de um template,
    preservando alinhamento, formatação de runs (bold/italic/underline/tamanho),
    espaçamento, indentação e tabelas.
    Suporta o placeholder {nova_pagina} para quebras de página.
    """
    try:
        doc_path = os.path.join(settings.BASE_DIR, 'pdf', template_name)
        document = docx.Document(doc_path)

        from docx.oxml.ns import qn as _qn
        html_content = []

        # Itera o body em ordem real (parágrafos e tabelas intercalados)
        for child in document.element.body:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag

            if tag == 'p':
                p = docx.text.paragraph.Paragraph(child, document)

                # Quebra de página explícita
                if '{nova_pagina}' in p.text:
                    html_content.append('<div class="manual-page-break"></div>')
                    continue

                # Parágrafo vazio: extrai só os estilos (alinhamento, line_spacing)
                # e usa &nbsp; para garantir que o browser respeite o height definido
                if not p.text.strip():
                    from docx.enum.text import WD_LINE_SPACING as WD_LS
                    alignment_map = {None: 'left', 0: 'left', 1: 'center', 2: 'right', 3: 'justify'}
                    pf = p.paragraph_format
                    sf = p.style.paragraph_format if p.style else None
                    alignment = alignment_map.get(_get_effective(pf, sf, 'alignment'), 'left')
                    empty_styles = [f'text-align: {alignment}', 'margin: 0', 'padding: 0']
                    try:
                        ls = _get_effective(pf, sf, 'line_spacing')
                        ls_rule = _get_effective(pf, sf, 'line_spacing_rule')
                        if ls is not None and ls_rule == WD_LS.EXACTLY:
                            ls_pt = ls.pt if hasattr(ls, 'pt') else ls / 12700
                            empty_styles.append(f'line-height: {ls_pt:.2f}pt')
                        elif ls is not None and isinstance(ls, (int, float)):
                            empty_styles.append(f'line-height: {ls}')
                    except Exception:
                        pass
                    html_content.append(f'<p style="{"; ".join(empty_styles)}">&nbsp;</p>')
                    continue

                html_content.append(_render_paragraph_html(p, context, template_name))

            elif tag == 'tbl':
                table = docx.table.Table(child, document)
                html_content.append(_render_table_html(table, context, template_name))

        return ''.join(html_content)

    except FileNotFoundError:
        error_msg = f'<p style="color: red;">ERRO: Template "{template_name}" não encontrado.</p>'
        logger.error(error_msg)
        return error_msg
    except Exception as e:
        error_msg = f'<p style="color: red;">ERRO ao processar o template "{template_name}": {e}</p>'
        logger.error(error_msg)
        return error_msg


def get_document_pages(patd, for_docx=False):
    """
    Gera uma LISTA de páginas de documento em HTML a partir dos templates.
    Cada item na lista representa um documento/seção separada.
    """
    base_context = _get_document_context(patd, for_docx=for_docx)
    document_pages_raw = []
    page_counter = 0
    pagina_alegacao_num = 0

    # 1. Documento Principal
    page_counter += 1
    document_pages_raw.append(_render_document_from_template('PATD_Coringa.docx', base_context))

    # 2. Alegação de Defesa (ou Preclusão)
    if patd.alegacao_defesa or patd.anexos.filter(tipo='defesa').exists():
        page_counter += 1
        pagina_alegacao_num = page_counter
        alegacao_context = base_context.copy()

        # --- INÍCIO DA CORREÇÃO: Restaurar HTML para visualização e manter placeholder para DOCX ---
        # 1. Gera o HTML para a visualização na página
        alegacao_html = _render_document_from_template('PATD_Alegacao_DF.docx', alegacao_context)
        # Substitui o placeholder do texto da alegação pelo conteúdo real, formatado para HTML
        alegacao_texto_html = (patd.alegacao_defesa or "").replace('\n', '<br>')
        alegacao_html = alegacao_html.replace('{Alegação de defesa}', alegacao_texto_html)
        document_pages_raw.append(alegacao_html)
        # --- FIM DA CORREÇÃO ---
        
        # SÓ adiciona a página de anexo se houver anexos de defesa
        if patd.anexos.filter(tipo='defesa').exists():
            document_pages_raw.append('<div class="manual-page-break"></div>')
            document_pages_raw.append("<p>{ANEXOS_DEFESA_PLACEHOLDER}</p>")

    # 3. Termo de Preclusão
    status_preclusao_e_posteriores = [
        'preclusao', 'apuracao_preclusao', 'aguardando_punicao',
        'aguardando_assinatura_npd', 'finalizado', 'aguardando_punicao_alterar', # 'aguardando_preenchimento_npd_reconsideracao' removido
        'analise_comandante', 'periodo_reconsideracao', 'em_reconsideracao',
        'aguardando_publicacao', 'aguardando_preenchimento_npd_reconsideracao',
        'aguardando_comandante_base'
    ]
    if not patd.alegacao_defesa and not patd.anexos.filter(tipo='defesa').exists() and patd.status in status_preclusao_e_posteriores:
        page_counter += 1
        pagina_alegacao_num = page_counter
        html_content = _render_document_from_template('PRECLUSAO.docx', base_context)
        html_content = f'<div data-document-id="alegacao_defesa">{html_content}</div>'
        document_pages_raw.append(html_content)

    # 4. Relatório de Apuração (sem o número da página ainda)
    if patd.justificado:
        page_counter += 1
        document_pages_raw.append(_render_document_from_template('RELATORIO_JUSTIFICADO.docx', base_context))
        # --- INÍCIO DA MODIFICAÇÃO: Interromper APÓS a lógica de duas passagens ---
        # Se a PATD foi justificada, o processo documental termina aqui.
        # Não há NPD, reconsideração, etc.
        # A lógica de contagem de páginas e substituição de placeholders abaixo
        # ainda precisa ser executada para que o relatório seja renderizado corretamente.
        # O 'return' foi movido para depois desse bloco.
        # --- FIM DA MODIFICAÇÃO ---

    elif patd.punicao_sugerida:
        page_counter += 1
        document_pages_raw.append(_render_document_from_template('RELATORIO_DELTA.docx', base_context))

    # 5. Nota de Punição Disciplinar (NPD)
    status_npd_e_posteriores = [
        'aguardando_assinatura_npd', 'finalizado', 'periodo_reconsideracao',
        'em_reconsideracao', 'aguardando_publicacao', 'aguardando_comandante_base' # 'aguardando_preenchimento_npd_reconsideracao' removido
    ]
    if patd.status in status_npd_e_posteriores and not patd.justificado:
        page_counter += 1
        document_pages_raw.append(_render_document_from_template('MODELO_NPD.docx', base_context))

    # 6. Reconsideração
    status_reconsideracao_e_posteriores = [
        'em_reconsideracao', 'aguardando_publicacao', 'finalizado',
        'aguardando_comandante_base', 'aguardando_nova_punicao',
    ]
    if patd.status in status_reconsideracao_e_posteriores and not patd.justificado:
         page_counter += 1
         reconsideracao_context = base_context.copy()
         if not patd.texto_reconsideracao and not patd.anexos.filter(tipo='reconsideracao').exists():
             reconsideracao_context['{Texto_reconsideracao}'] = '{Botao Adicionar Reconsideracao}'
         else:
             reconsideracao_context['{Texto_reconsideracao}'] = patd.texto_reconsideracao or "[Ver documentos anexos]"
         html_content = _render_document_from_template('MODELO_RECONSIDERACAO.docx', reconsideracao_context)
         
         # --- CORREÇÃO CRÍTICA ---
         html_content = html_content.replace('{Assinatura Militar Arrolado}', '{Assinatura Reconsideracao}')
         document_pages_raw.append(html_content)
         
         if patd.anexos.filter(tipo='reconsideracao').exists():
             document_pages_raw.append('<div class="manual-page-break"></div>')
             document_pages_raw.append("<p>{ANEXOS_RECONSIDERACAO_PLACEHOLDER}</p>")

    # 7. Anexos da reconsideração oficial
    status_anexo_reconsideracao_oficial = ['aguardando_publicacao', 'finalizado', 'aguardando_nova_punicao']
    if patd.status in status_anexo_reconsideracao_oficial:
        if patd.anexos.filter(tipo='reconsideracao_oficial').exists():
            document_pages_raw.append('<div class="manual-page-break"></div>')
            document_pages_raw.append("<p>{ANEXO_OFICIAL_RECONSIDERACAO_PLACEHOLDER}</p>")

    # 8. Nova NPD pós-reconsideração (quando nova punição já foi definida)
    if patd.nova_punicao_tipo and patd.status in ['aguardando_publicacao', 'finalizado']:
        page_counter += 1
        document_pages_raw.append(_render_document_from_template('MODELO_NPD_RECONSIDERACAO.docx', base_context))

    # --- INÍCIO DA LÓGICA DE DUAS PASSAGENS ---
    # 1. Primeira Passagem: Contar páginas físicas
    physical_page_count = 0
    alegacao_physical_page_num = 0
    
    for doc_html in document_pages_raw:
        # Conta as quebras de página manuais dentro do documento
        num_breaks = doc_html.count('<div class="manual-page-break"></div>')
        
        # Se este é o documento da alegação, registra o número da página atual
        if '<div data-document-id="alegacao_defesa">' in doc_html:
            alegacao_physical_page_num = physical_page_count + 1
            
        # Cada documento começa em uma nova página, e adiciona as quebras internas
        physical_page_count += (1 + num_breaks)

    # 2. Segunda Passagem: Substituir o placeholder com o número correto
    final_document_pages = []
    for doc_html in document_pages_raw:
        final_html = doc_html.replace('{pagina_alegacao}', f"{alegacao_physical_page_num:02d}")
        final_document_pages.append(final_html)
    # --- FIM DA LÓGICA DE DUAS PASSAGENS ---

    # --- INÍCIO DA MODIFICAÇÃO: Ponto de interrupção correto para justificação ---
    if patd.justificado:
        return final_document_pages
    # --- FIM DA MODIFICAÇÃO ---

    return final_document_pages


def _try_advance_status_from_justificativa(patd):
    """
    Verifica se a PATD no status 'aguardando_justificativa' pode avançar
    para 'em_apuracao'. Isso só deve ocorrer se tanto a alegação de defesa
    quanto todas as assinaturas necessárias estiverem presentes.
    """
    if patd.status != 'aguardando_justificativa':
        return False

    has_defesa = bool(patd.alegacao_defesa or patd.anexos.filter(tipo='defesa').exists())
    if not has_defesa:
        return False

    document_pages = get_document_pages(patd)
    raw_document_text = "".join(document_pages)
    required_signatures = raw_document_text.count('{Assinatura Militar Arrolado}')
    provided_signatures = sum(1 for s in (patd.assinaturas_militar or []) if s)

    if provided_signatures < required_signatures:
        logger.warning(f"PATD {patd.pk}: Tentativa de avançar de 'aguardando_justificativa', mas assinaturas de ciência incompletas ({provided_signatures}/{required_signatures}).")
        return False

    patd.status = 'em_apuracao'
    logger.info(f"PATD {patd.pk}: Avançando status de 'aguardando_justificativa' para 'em_apuracao'.")
    return True
