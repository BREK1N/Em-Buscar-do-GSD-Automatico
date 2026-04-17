import io, json, os, re, logging, base64, uuid, traceback
import tempfile
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.files.base import ContentFile
from django.core.files import File
from django.contrib.staticfiles.storage import staticfiles_storage
from django.contrib.staticfiles import finders
import docx
from docx import Document
from docx.shared import Cm, Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from bs4 import BeautifulSoup, NavigableString
import fitz

from ..models import PATD, Configuracao, Anexo
from Secao_pessoal.models import Efetivo
from .decorators import ouvidoria_required, oficial_responsavel_required, comandante_redirect
from .helpers import (
    _get_document_context, _render_document_from_template,
    get_document_pages, format_militar_string,
    _try_advance_status_from_justificativa,
)
from ..analise_transgressao import analisar_e_resumir_defesa, reescrever_ocorrencia

logger = logging.getLogger(__name__)

@login_required
@ouvidoria_required
@require_POST
def salvar_alegacao_defesa(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)

        if patd.alegacao_defesa or patd.anexos.filter(tipo='defesa').exists():
            return JsonResponse({
                'status': 'error',
                'message': 'A alegação de defesa já foi enviada e não pode ser alterada.'
            }, status=403)

        alegacao_texto = request.POST.get('alegacao_defesa', '')
        arquivos = request.FILES.getlist('anexos_defesa')

        if not alegacao_texto and not arquivos:
            return JsonResponse({'status': 'error', 'message': 'É necessário fornecer um texto ou anexar pelo menos um ficheiro.'}, status=400)

        patd.alegacao_defesa = alegacao_texto
        patd.data_alegacao = timezone.now()

        for arquivo in arquivos:
            Anexo.objects.create(patd=patd, arquivo=arquivo, tipo='defesa')

        try:
            if not patd.alegacao_defesa_resumo:
                patd.alegacao_defesa_resumo = analisar_e_resumir_defesa(patd.alegacao_defesa)
            if not patd.ocorrencia_reescrita:
                ocorrencia_formatada = reescrever_ocorrencia(patd.transgressao)
                patd.ocorrencia_reescrita = ocorrencia_formatada
                patd.comprovante = ocorrencia_formatada
        except Exception as e:
            logger.error(f"Erro ao chamar a IA para processar textos da PATD {pk}: {e}")
            if not patd.alegacao_defesa_resumo:
                patd.alegacao_defesa_resumo = "Erro ao gerar resumo."
            if not patd.ocorrencia_reescrita:
                patd.ocorrencia_reescrita = patd.transgressao
                patd.comprovante = patd.transgressao

        patd.save()
        _try_advance_status_from_justificativa(patd)
        patd.save()

        return JsonResponse({'status': 'success', 'message': 'Alegação de defesa e anexos salvos com sucesso.'})
    except Exception as e:
        logger.error(f"Erro ao salvar alegação de defesa da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@ouvidoria_required
@require_POST
def extender_prazo(request, pk):
    try:
        patd = get_object_or_404(PATD, pk=pk)
        if patd.status != 'prazo_expirado':
            return JsonResponse({'status': 'error', 'message': 'O prazo só pode ser estendido se estiver expirado.'}, status=400)

        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
        dias_extensao = int(data.get('dias', 0))
        minutos_extensao = int(data.get('minutos', 0))

        if not request.user.is_superuser and minutos_extensao != 0:
            return JsonResponse({'status': 'error', 'message': 'Apenas administradores podem alterar os minutos.'}, status=403)


        if dias_extensao < 0 or minutos_extensao < 0:
            return JsonResponse({'status': 'error', 'message': 'Valores de extensão de prazo inválidos.'}, status=400)

        config = Configuracao.load()

        delta_dias = config.prazo_defesa_dias - dias_extensao
        delta_minutos = config.prazo_defesa_minutos - minutos_extensao

        patd.data_ciencia = timezone.now() - timedelta(days=delta_dias, minutes=delta_minutos)
        patd.status = 'aguardando_justificativa'
        patd.save()

        return JsonResponse({'status': 'success', 'message': 'Prazo estendido com sucesso.'})

    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Dados de entrada inválidos.'}, status=400)
    except Exception as e:
        logger.error(f"Erro ao estender prazo da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Ocorreu um erro interno.'}, status=500)


@login_required
@ouvidoria_required
@require_POST
def salvar_documento_patd(request, pk):
    patd = get_object_or_404(PATD, pk=pk)

    # --- BLOQUEIO DE SEGURANÇA ---
    # Este bloco impede qualquer edição (Texto, Datas ou Localidade) se estiver finalizado.
    if patd.status == 'finalizado':
        return JsonResponse({
            'status': 'error', 
            'message': 'Este processo está finalizado e não permite mais edições no documento.'
        }, status=403)
        
    try:
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)

        # Obtém os dados
        texto_documento = data.get('texto_documento')
        dates = data.get('dates', {})
        texts = data.get('texts', {})

        # Validação básica
        if texto_documento is None:
            return JsonResponse({'status': 'error', 'message': 'Nenhum texto recebido.'}, status=400)

        # 1. Atualiza o texto do documento
        patd.documento_texto = texto_documento
        
        # 2. Atualiza a Localidade (Manipulação segura de JSONField)
        if 'localidade' in texts:
            # Garante que é um dicionário antes de editar
            circunstancias = patd.circunstancias if isinstance(patd.circunstancias, dict) else {}
            circunstancias['localidade'] = texts['localidade']
            patd.circunstancias = circunstancias # Reatribuição força o Django a reconhecer a mudança

        # 3. Atualiza as Datas dinamicamente
        for field_name, date_str in dates.items():
            # Só atualiza se o campo existir no modelo PATD para evitar erros
            if hasattr(patd, field_name):
                if date_str:
                    try:
                        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                        setattr(patd, field_name, date_obj)
                    except (ValueError, TypeError):
                        logger.warning(f"Formato de data inválido para o campo {field_name}: {date_str}")
                else:
                    # Se vier vazio, define como None (null no banco)
                    setattr(patd, field_name, None)

        patd.save()

        return JsonResponse({'status': 'success', 'message': 'Documento, datas e localidade salvos com sucesso.'})
        
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'JSON inválido.'}, status=400)
    except Exception as e:
        logger.error(f"Erro ao salvar documento da PATD {pk}: {e}")
        return JsonResponse({'status': 'error', 'message': 'Erro interno ao salvar.'}, status=500)


@login_required
@comandante_redirect
@ouvidoria_required
@require_POST
def upload_ficha_individual(request, pk):
    patd = get_object_or_404(PATD, pk=pk)

    if patd.status == 'finalizado':
        messages.error(request, "Não é possível anexar arquivos em processos finalizados.")
        return redirect('Ouvidoria:patd_detail', pk=pk)
    
    if 'ficha_individual' not in request.FILES:
        messages.error(request, "Nenhum arquivo enviado.")
        return redirect('Ouvidoria:patd_detail', pk=pk)

    ficha_individual_file = request.FILES['ficha_individual']

    # Remove existing ficha_individual if it exists
    patd.anexos.filter(tipo='ficha_individual').delete()

    # Create a new Anexo for the ficha_individual
    Anexo.objects.create(
        patd=patd,
        arquivo=ficha_individual_file,
        tipo='ficha_individual'
    )

    messages.success(request, "Ficha individual atualizada com sucesso.")
    return redirect('Ouvidoria:patd_detail', pk=pk)


def _append_anexo_content(document, anexo):
    """
    Função auxiliar para adicionar o conteúdo de um anexo (PDF, DOCX, Imagem)
    a um documento docx existente, sem adicionar uma quebra de página inicial.
    """
    file_path = anexo.arquivo.path
    file_name = os.path.basename(file_path)
    ext = os.path.splitext(file_name)[1].lower()
    
    try:
        if not os.path.exists(file_path):
            document.add_paragraph(f"[Erro: Ficheiro anexo '{file_name}' não encontrado no servidor.]")
            return

        if ext in ['.png', '.jpg', '.jpeg']:
            # Adiciona imagem, mantendo a proporção com largura máxima de 6 polegadas
            document.add_picture(file_path, width=Inches(6.5))
        
        elif ext == '.docx':
            # Anexa o conteúdo do DOCX, preservando a formatação
            sub_doc = docx.Document(file_path)
            for element in sub_doc.element.body:
                document.element.body.append(element)
        
        elif ext == '.pdf':
            try:
                pdf_doc = fitz.open(file_path)
                for page_num, page in enumerate(pdf_doc):
                    # Renderiza a página para um pixmap (imagem) com alta qualidade
                    pix = page.get_pixmap(dpi=200) # DPI ajustado para equilíbrio de qualidade/tamanho
                    img_bytes = pix.tobytes("png")
                    
                    img_stream = io.BytesIO(img_bytes)

                    # Adiciona a imagem ao docx, com uma largura que se ajuste à página
                    document.add_picture(img_stream, width=Inches(6.5))
                    
                    # Adiciona quebra de página entre as páginas do PDF
                    if page_num < len(pdf_doc) - 1:
                        document.add_page_break()

            except Exception as e:
                logger.error(f"Erro ao converter PDF para imagem {file_name}: {e}")
                document.add_paragraph(f"[Erro ao processar o anexo PDF '{file_name}' como imagem. O ficheiro pode estar corrompido ou ter um formato não suportado.]")

        else:
            # Tipo de ficheiro não suportado para embutir
            document.add_paragraph(f"[Conteúdo do anexo '{file_name}' (tipo: {ext}) não suportado para inclusão direta no DOCX.]")

    except Exception as e:
        logger.error(f"Erro geral ao processar anexo {file_name} para DOCX: {e}")
        document.add_paragraph(f"[Erro ao processar anexo '{file_name}': {e}]")


def add_page_number(paragraph):
    """
    Adiciona um campo de número de página a um parágrafo no rodapé.
    """
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT

    # Adiciona o texto "Página "
    run = paragraph.add_run()
    run.add_text('Página ')

    # --- INÍCIO DA CORREÇÃO ---
    # Cria o elemento fldChar para 'begin'
    fldChar_begin = docx.oxml.shared.OxmlElement('w:fldChar')
    fldChar_begin.set(docx.oxml.shared.qn('w:fldCharType'), 'begin')
    run._r.append(fldChar_begin)

    # Adiciona o código de instrução do campo (PAGE)
    instrText = docx.oxml.shared.OxmlElement('w:instrText')
    instrText.set(docx.oxml.shared.qn('xml:space'), 'preserve')
    instrText.text = 'PAGE'
    run._r.append(instrText)

    # Cria o elemento fldChar para 'end'
    fldChar_end = docx.oxml.shared.OxmlElement('w:fldChar')
    fldChar_end.set(docx.oxml.shared.qn('w:fldCharType'), 'end')
    run._r.append(fldChar_end)


def _append_alegacao_docx(document, patd, context):
    """Lê o template da alegação, substitui os placeholders e o anexa ao documento principal."""
    # --- INÍCIO DA CORREÇÃO ---
    # Reutiliza o mesmo regex da função principal para consistência
    placeholder_regex = re.compile(r'({[^}]+})')
    # --- FIM DA CORREÇÃO ---
    try:
        document.add_page_break()

        doc_path = os.path.join(settings.BASE_DIR, 'pdf', 'PATD_Alegacao_DF.docx')
        alegacao_doc = Document(doc_path)
        for source_p in alegacao_doc.paragraphs:
            if source_p.text.strip():
                new_p = document.add_paragraph()
                new_p.paragraph_format.alignment = source_p.paragraph_format.alignment

                text_to_process = source_p.text
                
                for placeholder, value in context.items():
                    text_to_process = text_to_process.replace(str(placeholder), str(value))

                # --- INÍCIO DA CORREÇÃO: Reutilizar lógica de processamento de placeholders e formatação ---
                # Divide o texto em partes de texto normal e placeholders
                # O regex agora inclui a formatação de negrito
                parts = re.split(r'(\*\*.*?\*\*|{[^}]+})', text_to_process)

                for part in parts:
                    if not part: continue

                    # Lógica para placeholders de imagem (assinaturas)
                    if placeholder_regex.match(part):
                        placeholder = part.strip()
                        is_image_placeholder = False
                        try:
                            if placeholder == '{Assinatura Alegacao Defesa}' and patd.assinatura_alegacao_defesa and patd.assinatura_alegacao_defesa.path and os.path.exists(patd.assinatura_alegacao_defesa.path):
                                new_p.add_run().add_picture(patd.assinatura_alegacao_defesa.path, height=Cm(1.5))
                                is_image_placeholder = True
                        except Exception as e:
                            logger.error(f"Erro ao processar placeholder de imagem na alegação: {placeholder}: {e}")
                        
                        if is_image_placeholder:
                            continue # Pula para a próxima parte se a imagem foi adicionada

                    # Lógica para o texto da alegação
                    if '{Alegação de defesa}' in part:
                        alegacao_text = patd.alegacao_defesa or "[ALEGAÇÃO NÃO FORNECIDA]"
                        lines = alegacao_text.splitlines()
                        for i, line in enumerate(lines):
                            if i > 0: new_p.add_run().add_break() # Adiciona quebra de linha
                            new_p.add_run(line)
                    # Lógica para texto em negrito
                    elif part.startswith('**') and part.endswith('**'):
                        new_p.add_run(part.strip('*')).bold = True
                    # Ignora outros placeholders que não são imagens
                    elif placeholder_regex.match(part):
                        continue
                    # Adiciona texto normal
                    else:
                        new_p.add_run(part)
                # --- FIM DA CORREÇÃO ---
    except Exception as e:
        logger.error(f"Erro ao anexar documento de alegação: {e}")
        document.add_paragraph(f"[ERRO AO PROCESSAR DOCUMENTO DE ALEGAÇÃO: {e}]")


def exportar_patd_docx(request, pk):


    """

    Gera e serve um ficheiro DOCX a partir do conteúdo HTML da PATD,

    incluindo imagens, formatação correta E ANEXOS.

    """


    patd = get_object_or_404(PATD, pk=pk)


    context = _get_document_context(patd, for_docx=True)


    config = Configuracao.load()


    comandante_gsd = config.comandante_gsd




    document = Document()




    # --- INÍCIO DA MODIFICAÇÃO: Adicionar proteção contra edição ---


    from docx.oxml.ns import qn


    from docx.oxml import OxmlElement




    # Obtém o elemento <w:settings> do documento


    doc_settings = document.settings.element


    # Cria o elemento <w:documentProtection> para tornar o documento somente leitura


    protection = OxmlElement('w:documentProtection')


    protection.set(qn('w:edit'), 'readOnly')


    doc_settings.append(protection)


    # --- FIM DA MODIFICAÇÃO ---




    style = document.styles['Normal']


    font = style.font


    font.name = 'Times New Roman'


    font.size = Pt(12)




    section = document.sections[0]


    section.top_margin = Cm(1.5)


    section.bottom_margin = Cm(2.54)


    section.left_margin = Cm(2.15)


    section.right_margin = Cm(2.5)


    section.gutter = Cm(0)




    # Adiciona o número da página no rodapé


    add_page_number(section.footer.paragraphs[0])


    

    full_html_content = "".join(get_document_pages(patd, for_docx=True))




    anexos_defesa = patd.anexos.filter(tipo='defesa')


    anexos_reconsideracao = patd.anexos.filter(tipo='reconsideracao')


    anexos_reconsideracao_oficial = patd.anexos.filter(tipo='reconsideracao_oficial')




    soup = BeautifulSoup(full_html_content, 'html.parser')




    militar_sig_counter = 0


    was_last_p_empty = False


    placeholder_regex = re.compile(r'({[^}]+})')




    for element in soup.find_all(['p', 'div']):


        if element.name == 'div' and 'manual-page-break' in element.get('class', []):


            document.add_page_break()


            was_last_p_empty = False


            continue




        if element.name == 'p':


            text_content_for_check = element.get_text().strip()




            # Lida com placeholders de anexo


            if "{ANEXOS_DEFESA_PLACEHOLDER}" in text_content_for_check and anexos_defesa.exists():


                for i, anexo in enumerate(anexos_defesa):


                    if i > 0:


                        document.add_page_break()


                    _append_anexo_content(document, anexo)


                continue


            if "{ANEXOS_RECONSIDERACAO_PLACEHOLDER}" in text_content_for_check and anexos_reconsideracao.exists():


                for i, anexo in enumerate(anexos_reconsideracao):


                    if i > 0:


                        document.add_page_break()


                    _append_anexo_content(document, anexo)


                continue


            if "{ANEXO_OFICIAL_RECONSIDERACAO_PLACEHOLDER}" in text_content_for_check and anexos_reconsideracao_oficial.exists():


                for i, anexo in enumerate(anexos_reconsideracao_oficial):


                    if i > 0:


                        document.add_page_break()


                    _append_anexo_content(document, anexo)


                continue




            embed_tag = element.find('embed')


            if embed_tag:


                embed_src = embed_tag.get('src')


                if embed_src:


                    # Encontra o anexo que corresponde a este src


                    anexo_to_append = None


                    # Percorre os anexos relevantes para encontrar a correspondência


                    for anexo in patd.anexos.filter(tipo__in=['oficio_lancamento', 'ficha_individual']):


                        if anexo.arquivo.url == embed_src:


                            anexo_to_append = anexo


                            break

                    

                    if anexo_to_append:


                        _append_anexo_content(document, anexo_to_append)


                continue




            is_empty_paragraph = not text_content_for_check and not element.find('img')


            

            if is_empty_paragraph:


                if not was_last_p_empty:


                    p = document.add_paragraph()


                    p.paragraph_format.space_before = Pt(0)


                    p.paragraph_format.space_after = Pt(0)


                    was_last_p_empty = True


                continue


            else:


                was_last_p_empty = False




            p = document.add_paragraph()


            p_format = p.paragraph_format


            p_format.line_spacing_rule = WD_LINE_SPACING.SINGLE


            p_format.space_before = Pt(0)


            p_format.space_after = Pt(0)


            

            is_signature_line = any(sig_placeholder in text_content_for_check for sig_placeholder in ['{Assinatura', '[LOCAL DA ASSINATURA/AÇÃO]'])


            is_short_line = len(text_content_for_check) < 80




            if element.has_attr('style'):


                if 'text-align: center' in element['style']:


                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER


                elif 'text-align: right' in element['style']:


                    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT


                elif 'text-align: justify' in element['style'] and not is_signature_line and not is_short_line:


                    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY




            for content in element.contents:


                if isinstance(content, NavigableString):


                    text_content = str(content)


                    parts = placeholder_regex.split(text_content)


                    for part in parts:


                        if not part: continue


                        is_image_placeholder = False


                        if placeholder_regex.match(part):


                            placeholder = part.strip()


                            try:


                                if placeholder == '{Assinatura_Imagem_Comandante_GSD}' and comandante_gsd and comandante_gsd.assinatura:


                                    _, img_str = comandante_gsd.assinatura.split(';base64,')


                                    p.add_run().add_picture(io.BytesIO(base64.b64decode(img_str)), height=Cm(1.5))


                                    is_image_placeholder = True


                                elif placeholder == '{Assinatura_Imagem_Oficial_Apurador}' and patd.assinatura_oficial and patd.assinatura_oficial.path and os.path.exists(patd.assinatura_oficial.path):


                                    p.add_run().add_picture(patd.assinatura_oficial.path, height=Cm(1.5))


                                    is_image_placeholder = True


                                elif placeholder == '{Assinatura_Imagem_Testemunha_1}' and patd.assinatura_testemunha1 and patd.assinatura_testemunha1.path and os.path.exists(patd.assinatura_testemunha1.path):


                                    p.add_run().add_picture(patd.assinatura_testemunha1.path, height=Cm(1.5))


                                    is_image_placeholder = True


                                elif placeholder == '{Assinatura_Imagem_Testemunha_2}' and patd.assinatura_testemunha2 and patd.assinatura_testemunha2.path and os.path.exists(patd.assinatura_testemunha2.path):


                                    p.add_run().add_picture(patd.assinatura_testemunha2.path, height=Cm(1.5))


                                    is_image_placeholder = True


                                elif placeholder == '{Assinatura Militar Arrolado}':


                                    assinaturas_arrolado = patd.assinaturas_militar or []


                                    if militar_sig_counter < len(assinaturas_arrolado) and assinaturas_arrolado[militar_sig_counter]:


                                        anexo_url = assinaturas_arrolado[militar_sig_counter]


                                        anexo_path = os.path.join(settings.MEDIA_ROOT, anexo_url.replace(settings.MEDIA_URL, '', 1))


                                        if os.path.exists(anexo_path):


                                            p.add_run().add_picture(anexo_path, height=Cm(1.5))


                                        militar_sig_counter += 1


                                        is_image_placeholder = True


                                    else:


                                          militar_sig_counter += 1


                                elif placeholder == '{Assinatura Alegacao Defesa}' and patd.assinatura_alegacao_defesa and patd.assinatura_alegacao_defesa.path and os.path.exists(patd.assinatura_alegacao_defesa.path):


                                     p.add_run().add_picture(patd.assinatura_alegacao_defesa.path, height=Cm(1.5))


                                     is_image_placeholder = True


                                elif placeholder == '{Assinatura Reconsideracao}' and patd.assinatura_reconsideracao and patd.assinatura_reconsideracao.path and os.path.exists(patd.assinatura_reconsideracao.path):


                                     p.add_run().add_picture(patd.assinatura_reconsideracao.path, height=Cm(1.5))


                                     is_image_placeholder = True


                                elif placeholder in ['{Botao Assinar Oficial}', '{Botao Assinar Testemunha 1}', '{Botao Assinar Testemunha 2}', '{Botao Adicionar Alegacao}', '{Botao Adicionar Reconsideracao}', '{Botao Definir Nova Punicao}', '{Botao Assinar Defesa}', '{Botao Assinar Reconsideracao}']: # Botões não devem ser renderizados como imagem


                                    is_image_placeholder = True


                                    p.add_run("[LOCAL DA ASSINATURA/AÇÃO]")


                            except Exception as e:


                                logger.error(f"Error processing image placeholder {placeholder}: {e}")


                                p.add_run(f"[{placeholder} - ERRO AO PROCESSAR]")


                                is_image_placeholder = False


                        if not is_image_placeholder:


                            sub_parts = re.split(r'(\*\*.*?\*\*)', part)


                            for sub_part in sub_parts:


                                if sub_part.startswith('**') and sub_part.endswith('**'):


                                    p.add_run(sub_part.strip('*')).bold = True


                                else:


                                    p.add_run(sub_part)


                elif content.name == 'img' and 'brasao.png' in content.get('src', ''):


                    img_path = finders.find('img/brasao.png')


                    if img_path and os.path.exists(img_path):


                        p.alignment = WD_ALIGN_PARAGRAPH.CENTER


                        p.add_run().add_picture(img_path, width=Cm(3))


                        was_last_p_empty = False


                elif content.name == 'strong':


                    p.add_run(content.get_text()).bold = True


                elif content.name == 'br':


                    p.add_run().add_break()

    
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')
    response['Content-Disposition'] = f'attachment; filename=PATD_{patd.numero_patd}.docx'
    document.save(response)

    return response


