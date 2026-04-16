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
        oficio_lancamento_html = f'<embed src="{oficio_anexo.arquivo.url}" type="application/pdf" width="100%" height="800px" />'

    # Adiciona a ficha individual ao contexto, se existir
    ficha_individual_anexo = patd.anexos.filter(tipo='ficha_individual').first()
    ficha_individual_html = ''
    if ficha_individual_anexo:
        ficha_individual_html = f'<embed src="{ficha_individual_anexo.arquivo.url}" type="application/pdf" width="100%" height="800px" />'

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


def _render_document_from_template(template_name, context):
    """
    Função genérica para renderizar um documento .docx a partir de um template,
    preservando o alinhamento e convertendo para HTML.
    AGORA SUPORTA O PLACEHOLDER {nova_pagina}
    """
    try:
        doc_path = os.path.join(settings.BASE_DIR, 'pdf', template_name)
        document = docx.Document(doc_path)

        alignment_map = {
            None: 'left',
            0: 'left',
            1: 'center',
            2: 'right',
            3: 'justify'
        }

        html_content = []

        for p in document.paragraphs:
            # --- NOVA VERIFICAÇÃO DE QUEBRA DE PÁGINA ---
            if '{nova_pagina}' in p.text:
                html_content.append('<div class="manual-page-break"></div>')
                continue # Pula para o próximo parágrafo
            # --- FIM DA VERIFICAÇÃO ---

            inline_text = p.text

            # --- INÍCIO DA NOVA LÓGICA ---
            # Substitui o "à fl. XX" hardcoded pelo nosso placeholder dinâmico
            if 'RELATORIO_DELTA' in template_name or 'RELATORIO_JUSTIFICADO' in template_name:
                # Este regex procura por "à fl." seguido de espaço(s), número(s), e depois vírgula, ponto ou espaço.
                inline_text = re.sub(r'(à fl\.)(\s*\d+\s*)([\,\.\s])', r'\1 {pagina_alegacao}\3', inline_text)
            # --- FIM DA NOVA LÓGICA ---

            # --- INÍCIO DA CORREÇÃO: Substituição direta sem escapar HTML ---
            # A lógica de escape foi removida. Os placeholders são substituídos diretamente.
            for placeholder, value in context.items():
                inline_text = inline_text.replace(str(placeholder), str(value))
            # --- FIM DA CORREÇÃO ---
            
            # **INÍCIO DA CORREÇÃO**
            # Tenta obter o alinhamento direto do parágrafo
            effective_alignment = p.paragraph_format.alignment
            # Se não houver alinhamento direto, herda do estilo
            if effective_alignment is None and p.style and p.style.paragraph_format:
                effective_alignment = p.style.paragraph_format.alignment
            # **FIM DA CORREÇÃO**

            alignment = alignment_map.get(effective_alignment, 'left')

            # Adiciona o parágrafo com o conteúdo já processado
            html_content.append(f'<p style="text-align: {alignment};">{inline_text}</p>')

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
        'aguardando_comandante_base' # 'aguardando_preenchimento_npd_reconsideracao' removido
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
    status_anexo_reconsideracao_oficial = ['aguardando_publicacao', 'finalizado']
    if patd.status in status_anexo_reconsideracao_oficial:
        # SÓ adiciona a página de anexo se houver anexos de reconsideração oficial
        if patd.anexos.filter(tipo='reconsideracao_oficial').exists():
            document_pages_raw.append('<div class="manual-page-break"></div>')
            document_pages_raw.append("<p>{ANEXO_OFICIAL_RECONSIDERACAO_PLACEHOLDER}</p>")

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
