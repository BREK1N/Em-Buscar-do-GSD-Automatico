import pandas as pd
import os
import tempfile
import httpx
import random
import unicodedata
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from Secao_pessoal.models import Efetivo, Posto, Quad, Especializacao, OM, Setor, Subsetor, Notificacao
from .forms import MilitarForm, NotificacaoForm
from django.contrib import messages
from django.db.models import Q, Max, Case, When, Value, IntegerField, Count
import json

def is_s1_member(user):
    """Check if the user is a member of the 'S1' group."""
    return user.groups.filter(name='S1').exists()

s1_required = user_passes_test(is_s1_member)



@s1_required
def index(request):
    return render(request, 'Secao_pessoal/index.html')

#Efetivo

@method_decorator(s1_required, name='dispatch')
class MilitarListView(ListView):
    model = Efetivo
    template_name = 'Secao_pessoal/militar_list.html'
    context_object_name = 'militares'
    ordering = ['nome_guerra']
    paginate_by = 20

    def get_template_names(self):
        if self.request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return ['Secao_pessoal/militar_list_partial.html']
        return ['Secao_pessoal/militar_list.html']

    def get_queryset(self):
        query = self.request.GET.get('q')
        rank_order = Case(
            When(posto='CL', then=Value(0)), When(posto='TC', then=Value(1)), When(posto='MJ', then=Value(2)), When(posto='CP', then=Value(3)),
            When(posto='1T', then=Value(4)), When(posto='2T', then=Value(5)),When(posto='ASP', then=Value (6)), When(posto='SO', then=Value(7)),
            When(posto='1S', then=Value(8)), When(posto='2S', then=Value(9)), When(posto='3S', then=Value(10)),
            When(posto='CB', then=Value(11)), When(posto='S1', then=Value(12)), When(posto='S2', then=Value(13)),When(posto='REC', then=Value(14)),
            default=Value(99), output_field=IntegerField(),
        )
        qs = super().get_queryset().annotate(rank_order=rank_order).order_by('rank_order', 'turma', 'nome_completo')
        if query:
            qs = qs.filter(
                Q(nome_completo__icontains=query) |
                Q(nome_guerra__icontains=query) |
                Q(saram__icontains=query) |
                Q(posto__icontains=query)
            )
        return qs
    
@method_decorator(s1_required, name='dispatch')
class MilitarCreateView(CreateView):
    model = Efetivo
    form_class = MilitarForm
    template_name = 'Secao_pessoal/militar_form.html'
    success_url = reverse_lazy('Secao_pessoal:militar_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Adicionar Militar'
        return context

@method_decorator(s1_required, name='dispatch')
class MilitarUpdateView(UpdateView):
    model = Efetivo
    form_class = MilitarForm
    template_name = 'Secao_pessoal/militar_form.html'
    success_url = reverse_lazy('Secao_pessoal:militar_list')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['titulo'] = 'Editar Militar'
        return context

@method_decorator(s1_required, name='dispatch')
class MilitarDeleteView(DeleteView):
    model = Efetivo
    template_name = 'Secao_pessoal/militar_confirm_delete.html'
    success_url = reverse_lazy('Secao_pessoal:militar_list')

#EFETIVO IMPORT EXCEL
@s1_required
def importar_excel(request):
    if request.method == 'POST' and request.FILES.get('excel_file'):
        excel_file = request.FILES['excel_file']
        
        try:
            # Lê o arquivo Excel e converte tudo para string para evitar erros de tipo
            df = pd.read_excel(excel_file, dtype=str)
            
            # Remove espaços em branco dos nomes das colunas
            df.columns = df.columns.str.strip()
            
            # Substitui valores 'nan' (vazios) do pandas por string vazia
            df.fillna('', inplace=True)

            criados = 0
            atualizados = 0

            for index, row in df.iterrows():
                # Pega o SARAM e remove espaços extras
                saram_valor = str(row.get('SARAM', '')).strip()
                
                # Se não tiver SARAM, pula a linha
                if not saram_valor:
                    continue

                # Dicionário com os dados a serem salvos/atualizados
                # AJUSTE AQUI: O lado esquerdo é o campo do seu Modelo, o direito é a coluna do Excel
                dados_militar = {
                    'posto': row.get('PST.', '').strip(),
                    'quad': row.get('QUAD.', '').strip(),
                    'especializacao': row.get('ESP.', '').strip(),
                    'saram': row.get('SARAM', '').strip(),
                    'nome_completo': row.get('NOME COMPLETO', '').strip(),
                    'nome_guerra': row.get('NOME DE GUERRA', '').strip(),
                    'turma': row.get('TURMA', '').strip(),
                    'situacao': row.get('SITUAÇÃO', '').strip(),
                    'om': row.get('OM', '').strip(),
                    'setor': row.get('SETOR', '').strip(),
                    'subsetor': row.get('SUBSETOR', '').strip()                    

                }

                # update_or_create busca pelo SARAM. Se achar, atualiza. Se não, cria.
                obj, created = Efetivo.objects.update_or_create(
                    saram=saram_valor,
                    defaults=dados_militar
                )

                if created:
                    criados += 1
                else:
                    atualizados += 1

            messages.success(request, f'Sucesso! {criados} militares criados e {atualizados} atualizados.')
            return redirect('Secao_pessoal:militar_list') # Verifique o nome da sua rota de listagem

        except Exception as e:
            messages.error(request, f'Erro na importação: {str(e)}')
            return redirect('Secao_pessoal:importar_excel')

    return render(request, 'Secao_pessoal/importar_excel.html')
    
# --- Lógica para Nome de Guerra ---

def normalize_name(name):
    """Remove acentos e caracteres especiais para comparação (ex: 'Corrêa' -> 'CORREA')."""
    if not name:
        return ""
    return ''.join(c for c in unicodedata.normalize('NFD', name) if unicodedata.category(c) != 'Mn').upper()

def gerar_sugestoes_guerra(nome_completo):
    """Gera uma lista de possíveis nomes de guerra baseados no nome completo, em ordem de prioridade."""
    ignore = ['de', 'da', 'do', 'dos', 'das', 'e']
    partes = [p for p in nome_completo.split() if p.lower() not in ignore]
    
    if not partes:
        return []
    
    sugestoes = []
    
    def add_unique(nome):
        nome = nome.upper()
        if nome not in sugestoes:
            sugestoes.append(nome)
    
    # 1. Último nome (Padrão)
    add_unique(partes[-1])
    
    # 2. Penúltimo (se houver e não for o primeiro)
    if len(partes) > 2:
        add_unique(partes[-2])

    # 3. Nomes Compostos (ex: Del Puerto, Villas Boas)
    if len(partes) >= 2:
        add_unique(f"{partes[-2]} {partes[-1]}")

    # 4. Primeiro + Último (Prioriza abreviação se o nome for longo)
    primeiro_ultimo = f"{partes[0]} {partes[-1]}"
    inicial_ultimo = f"{partes[0][0]}. {partes[-1]}"
    
    if len(partes[0]) > 5: # Ex: Leonardo (8) -> L. MARTINS
        add_unique(inicial_ultimo)
        add_unique(primeiro_ultimo)
    else:
        add_unique(primeiro_ultimo)
        add_unique(inicial_ultimo)
    
    # 5. Outras combinações
    if len(partes) > 2:
        primeiro_penultimo = f"{partes[0]} {partes[-2]}"
        inicial_penultimo = f"{partes[0][0]}. {partes[-2]}"
        
        if len(partes[0]) > 5:
            add_unique(inicial_penultimo)
            add_unique(primeiro_penultimo)
        else:
            add_unique(primeiro_penultimo)
            add_unique(inicial_penultimo)

    for i in range(1, len(partes)-1):
        add_unique(partes[i])
        # Adiciona combinações com nomes do meio, também verificando tamanho
        comb_nome = f"{partes[0]} {partes[i]}"
        comb_inicial = f"{partes[0][0]}. {partes[i]}"
        
        if len(partes[0]) > 5:
            add_unique(comb_inicial)
            add_unique(comb_nome)
        else:
            add_unique(comb_nome)
            add_unique(comb_inicial)

    return sugestoes

@s1_required
def nome_de_guerra(request):
    if request.method == 'POST':
        try:
            # 1. Buscar Recrutas no Banco de Dados
            recrutas = Efetivo.objects.filter(posto='REC')
            
            if not recrutas.exists():
                messages.warning(request, "Nenhum militar com posto 'REC' encontrado no efetivo.")
                return redirect('Secao_pessoal:nome_de_guerra')

            # Carrega todos os nomes existentes e normaliza para comparação rápida e sem acentos
            existing_names_map = {}
            all_efetivo = Efetivo.objects.exclude(nome_guerra__isnull=True).exclude(nome_guerra='').values('id', 'nome_guerra')
            
            for item in all_efetivo:
                norm = normalize_name(item['nome_guerra'])
                if norm not in existing_names_map:
                    existing_names_map[norm] = set()
                existing_names_map[norm].add(item['id'])

            nomes_usados_sessao_norm = set() # Rastreia nomes gerados nesta sessão (normalizados)
            count_atualizados = 0

            for recruta in recrutas:
                sugestoes = gerar_sugestoes_guerra(recruta.nome_completo)
                nome_final = None
                
                for sugestao in sugestoes:
                    sugestao_norm = normalize_name(sugestao)
                    
                    # Verifica conflito no DB (se existe e não é o próprio recruta)
                    ids_com_esse_nome = existing_names_map.get(sugestao_norm, set())
                    conflito_db = bool(ids_com_esse_nome - {recruta.pk})
                    
                    # Verifica conflito na sessão atual
                    conflito_sessao = sugestao_norm in nomes_usados_sessao_norm

                    if not conflito_db and not conflito_sessao:
                        nome_final = sugestao
                        break
                
                if not nome_final:
                    base = sugestoes[0] if sugestoes else "MILITAR"
                    contador = 2
                    while True:
                        teste = f"{base} {contador}"
                        teste_norm = normalize_name(teste)
                        
                        ids_com_esse_nome = existing_names_map.get(teste_norm, set())
                        conflito_db = bool(ids_com_esse_nome - {recruta.pk})
                        conflito_sessao = teste_norm in nomes_usados_sessao_norm

                        if not conflito_db and not conflito_sessao:
                            nome_final = teste
                            break
                        contador += 1

                nomes_usados_sessao_norm.add(normalize_name(nome_final))

                # Atualiza diretamente no banco de dados
                recruta.nome_guerra = nome_final
                recruta.save()
                count_atualizados += 1
            
            messages.success(request, f"Sucesso! Nomes de guerra atualizados para {count_atualizados} recrutas.")
            return redirect('Secao_pessoal:nome_de_guerra')
            
        except Exception as e:
            messages.error(request, f"Erro ao gerar nomes: {str(e)}")
            return redirect('Secao_pessoal:nome_de_guerra')

    return render(request, 'Secao_pessoal/nome_de_guerra.html')

@login_required
def comunicacoes(request):
    """
    View para listar notificações recebidas e, se for S1, enviar novas.
    """
    try:
        militar_logado = request.user.profile.militar
    except:
        messages.error(request, "Seu usuário não está vinculado a um militar.")
        return redirect('Secao_pessoal:index')

    # Processar envio de notificação (Apenas S1)
    form = None
    is_s1 = is_s1_member(request.user)
    
    if is_s1:
        if request.method == 'POST':
            form = NotificacaoForm(request.POST)
            if form.is_valid():
                notificacao = form.save(commit=False)
                notificacao.remetente = militar_logado
                notificacao.save()
                messages.success(request, f"Notificação enviada para {notificacao.destinatario.nome_guerra}.")
                return redirect('Secao_pessoal:comunicacoes')
        else:
            form = NotificacaoForm()

    # Listar notificações (Caixa de Entrada ou Enviados)
    box = request.GET.get('box', 'inbox')
    
    if box == 'sent':
        notificacoes = Notificacao.objects.filter(remetente=militar_logado).order_by('-data_criacao')
    else:
        notificacoes = Notificacao.objects.filter(destinatario=militar_logado).order_by('-data_criacao')
    
    # Marcar como lida se solicitado via GET (simples) ou via AJAX (idealmente)
    if request.GET.get('ler') and box == 'inbox':
        try:
            notif_id = int(request.GET.get('ler'))
            notif = Notificacao.objects.get(id=notif_id, destinatario=militar_logado)
            notif.lida = True
            notif.save()
            return redirect('Secao_pessoal:comunicacoes')
        except:
            pass

    context = {
        'notificacoes': notificacoes,
        'form': form,
        'is_s1': is_s1,
        'current_box': box
    }
    return render(request, 'Secao_pessoal/comunicacoes.html', context)

@s1_required
def troca_de_setor(request):
    # Lembre-se de criar o arquivo: templates/Secao_pessoal/troca_de_setor.html
    return render(request, 'Secao_pessoal/troca_de_setor.html')

@s1_required
def gerenciar_opcoes(request):
    # Dicionário que mapeia o 'tipo' do formulário para a Model correspondente
    MAPA_OPCOES = {
        'posto': Posto,
        'quad': Quad,
        'especializacao': Especializacao,
        'om': OM,
        'setor': Setor,
        'subsetor': Subsetor,
    }

    if request.method == 'POST':
        action = request.POST.get('action')
        tipo_opcao = request.POST.get('tipo_opcao') # Pega o tipo de opção para o redirect
        
        # Ação para ADICIONAR um novo item
        if action == 'add':
            nome = request.POST.get('nome', '').strip()
            
            if tipo_opcao in MAPA_OPCOES and nome:
                model = MAPA_OPCOES[tipo_opcao]
                # 'get_or_create' evita duplicatas
                obj, created = model.objects.get_or_create(nome=nome)
                if created:
                    messages.success(request, f'Opção "{nome}" adicionada com sucesso.')
                else:
                    messages.warning(request, f'Opção "{nome}" já existia.')
            else:
                messages.error(request, 'Erro ao adicionar a opção. Verifique os dados.')

        # Ação para DELETAR um item
        elif action == 'delete':
            item_id = request.POST.get('item_id')

            if tipo_opcao in MAPA_OPCOES and item_id:
                model = MAPA_OPCOES[tipo_opcao]
                try:
                    item = model.objects.get(id=item_id)
                    item_nome = item.nome
                    item.delete()
                    messages.success(request, f'Opção "{item_nome}" removida com sucesso.')
                except model.DoesNotExist:
                    messages.error(request, 'Erro: A opção que você tentou remover não existe.')

        # Redireciona para a mesma página, mantendo o tipo selecionado na URL
        redirect_url = reverse_lazy('Secao_pessoal:gerenciar_opcoes')
        if tipo_opcao:
            return redirect(f'{redirect_url}?tipo={tipo_opcao}')
        return redirect(redirect_url)

    # Contexto para o método GET (carregamento da página)
    context = {
        'postos': Posto.objects.all(),
        'quads': Quad.objects.all(),
        'especializacoes': Especializacao.objects.all(),
        'oms': OM.objects.all(),
        'setores': Setor.objects.all(),
        'subsetores': Subsetor.objects.all(),
        'selected_tipo': request.GET.get('tipo', 'posto'), # Pega da URL ou define um padrão
    }
    return render(request, 'Secao_pessoal/gerenciar_opcoes.html', context)

@login_required
def api_notificacoes_check(request):
    """Retorna JSON com contagem de notificações não lidas para o header"""
    try:
        if hasattr(request.user, 'profile') and request.user.profile.militar:
            militar = request.user.profile.militar
            nao_lidas = Notificacao.objects.filter(destinatario=militar, lida=False)
            count = nao_lidas.count()
            
            data = []
            for n in nao_lidas[:5]: # Retorna as 5 mais recentes para o preview
                data.append({
                    'id': n.id,
                    'titulo': n.titulo,
                    'remetente': n.remetente.nome_guerra,
                    'data': n.data_criacao.strftime('%d/%m %H:%M')
                })
            
            return HttpResponse(json.dumps({'count': count, 'notifications': data}), content_type="application/json")
    except Exception as e:
        pass
    
    return HttpResponse(json.dumps({'count': 0, 'notifications': []}), content_type="application/json")

# Nota: Você precisará adicionar 'import json' no topo do arquivo views.py se ainda não existir.