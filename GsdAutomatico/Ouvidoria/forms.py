from django import forms
from .models import PATD
from Secao_pessoal.models import Efetivo
import json
import re
from num2words import num2words

class AtribuirOficialForm(forms.ModelForm):
    class Meta:
        model = PATD
        fields = ['oficial_responsavel']
        labels = {
            'oficial_responsavel': 'Selecione o Oficial para Atribuir'
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['oficial_responsavel'].queryset = Efetivo.objects.filter(oficial=True).order_by('posto', 'nome_guerra')
        self.fields['oficial_responsavel'].empty_label = "--- Selecione um Oficial ---"

class AceitarAtribuicaoForm(forms.Form):
    senha = forms.CharField(widget=forms.PasswordInput, label="Sua Senha de Acesso")

class ComandanteAprovarForm(forms.Form):
    """
    Formulário para o comandante confirmar uma ação (ex: aprovar PATD)
    inserindo a própria senha.
    """
    senha_comandante = forms.CharField(widget=forms.PasswordInput, label="Sua Senha")

class MilitarForm(forms.ModelForm):
    # Formulário para criar e atualizar registros de Militares.
    class Meta:
        model = Efetivo
        fields = [
            'posto', 'quad', 'especializacao', 'saram', 'nome_completo',
            'nome_guerra', 'turma', 'situacao', 'om', 'setor', 'subsetor', 'oficial',
            'assinatura' # Campo adicionado para futuras implementações
        ]
        widgets = {
            'posto': forms.TextInput(attrs={'placeholder': 'Ex: Capitão'}),
            'quad': forms.TextInput(attrs={'placeholder': 'Ex: QOAV'}),
            'especializacao': forms.TextInput(attrs={'placeholder': 'Ex: Aviador'}),
            'saram': forms.NumberInput(attrs={'placeholder': 'Apenas números'}),
            'nome_completo': forms.TextInput(attrs={'placeholder': 'Nome completo do militar'}),
            'nome_guerra': forms.TextInput(attrs={'placeholder': 'Nome de guerra'}),
            'turma': forms.TextInput(attrs={'placeholder': 'Ex: 2024'}),
            'situacao': forms.TextInput(attrs={'placeholder': 'Ex: Ativo'}),
            'om': forms.TextInput(attrs={'placeholder': 'Ex: CINDACTA IV'}),
            'setor': forms.TextInput(attrs={'placeholder': 'Ex: Divisão de Operações'}),
            'subsetor': forms.TextInput(attrs={'placeholder': 'Ex: Seção de Busca e Salvamento'}),
            'assinatura': forms.HiddenInput(), # Oculto por enquanto
        }

class PATDForm(forms.ModelForm):
    """
    Formulário para editar uma PATD existente, incluindo campos da apuração.
    """
    # --- CAMPOS MELHORADOS ---
    itens_enquadrados_text = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5}),
        required=False,
        label="Itens Enquadrados",
        help_text="Edite os itens, um por linha. Formato: 'Número: Descrição'"
    )
    atenuantes = forms.CharField(
        required=False,
        label="Atenuantes",
        help_text="Circunstâncias atenuantes, separadas por vírgula (ex: a, b, c)."
    )
    agravantes = forms.CharField(
        required=False,
        label="Agravantes",
        help_text="Circunstâncias agravantes, separadas por vírgula (ex: a, b, c)."
    )
    # --- INÍCIO DA MODIFICAÇÃO: Campos para Punição Sugerida ---
    punicao_sugerida_dias = forms.IntegerField(
        required=False,
        min_value=0,
        label="Punição Sugerida (Dias)",
        help_text="Número de dias para a punição sugerida pela IA.",
        widget=forms.NumberInput(attrs={'placeholder': 'Ex: 6'})
    )
    punicao_sugerida_tipo = forms.ChoiceField(
        required=False,
        label="Punição Sugerida (Tipo)",
        choices=[('', '---------'), ('detenção', 'Detenção'), ('prisão', 'Prisão'), ('repreensão', 'Repreensão')],
        help_text="Tipo da punição sugerida pela IA."
    )
    # --- FIM DA MODIFICAÇÃO ---

    # --- NOVO CAMPO NUMÉRICO PARA DIAS DA NOVA PUNIÇÃO ---
    nova_punicao_dias_num = forms.IntegerField(
        required=False,
        min_value=0,
        label="Nova Punição (Dias - Numérico)",
        help_text="Digite o número de dias para a punição pós-reconsideração.",
        widget=forms.NumberInput(attrs={'placeholder': 'Ex: 2'})
    )

    class Meta:
        model = PATD
        # --- CAMPOS ADICIONADOS AQUI ---
        fields = [
            'status', 'transgressao', 'oficial_responsavel', 'testemunha1', 'testemunha2',
            'data_ocorrencia', 'itens_enquadrados_text', 'atenuantes', 'agravantes', 'comprovante',
            'punicao_sugerida_dias', 'punicao_sugerida_tipo',
            'transgressao_afirmativa', 'natureza_transgressao', 'comportamento',
            'alegacao_defesa_resumo', 'ocorrencia_reescrita', 'texto_relatorio',
            'nova_punicao_dias_num', 'nova_punicao_tipo' # Adicionados aqui
        ]
        # --- FIM DA ADIÇÃO DE CAMPOS ---

        widgets = {
            'transgressao': forms.Textarea(attrs={'rows': 4}),
            'data_ocorrencia': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'comprovante': forms.Textarea(attrs={'rows': 3}),
            'transgressao_afirmativa': forms.Textarea(attrs={'rows': 3}),
            'alegacao_defesa_resumo': forms.Textarea(attrs={'rows': 3}),
            'ocorrencia_reescrita': forms.Textarea(attrs={'rows': 3}),
            'texto_relatorio': forms.Textarea(attrs={'rows': 5}),
            # --- WIDGET ADICIONADO ---
            'nova_punicao_tipo': forms.Select(choices=[ # Define as opções diretamente
                ('', '---------'), # Opção vazia
                ('detenção', 'Detenção'),
                ('prisão', 'Prisão'),
                ('repreensão', 'Repreensão'),
            ]),
        }
        labels = {
            'status': "Status Atual",
            'transgressao': "Descrição da Transgressão",
            'oficial_responsavel': "Oficial Responsável",
            'testemunha1': "1ª Testemunha",
            'testemunha2': "2ª Testemunha",
            'data_ocorrencia': "Data da Ocorrência",
            'comprovante': "Comprovante da Transgressão",
            # 'dias_punicao': "Dias de Punição", # Ocultado
            # 'punicao': "Punição", # Ocultado
            'transgressao_afirmativa': "Transgressão Afirmativa",
            'natureza_transgressao': "Natureza da Transgressão",
            'comportamento': "Comportamento",
            'alegacao_defesa_resumo': "Resumo da Alegação de Defesa",
            'ocorrencia_reescrita': "Ocorrência Reescrita (IA)",
            'texto_relatorio': "Texto do Relatório (IA)",
            # --- LABELS ADICIONADOS ---
            # 'nova_punicao_dias_num' já tem label no campo
            'nova_punicao_tipo': "Nova Punição (Tipo)"
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra a lista de militares para testemunhas
        queryset_testemunhas = Efetivo.objects.filter(subsetor='OUVIDORIA')
        self.fields['testemunha1'].queryset = queryset_testemunhas
        self.fields['testemunha1'].empty_label = "--- Selecione ---"
        self.fields['testemunha2'].queryset = queryset_testemunhas
        self.fields['testemunha2'].empty_label = "--- Selecione ---"
        self.fields['status'].disabled = True

        # Preenche os campos de texto com os dados JSON formatados
        if self.instance and self.instance.pk:
            if self.instance.itens_enquadrados:
                itens_str = "\n".join([f"{item.get('numero', '')}: {item.get('descricao', '')}" for item in self.instance.itens_enquadrados])
                self.fields['itens_enquadrados_text'].initial = itens_str

            if self.instance.circunstancias:
                self.fields['atenuantes'].initial = ", ".join(self.instance.circunstancias.get('atenuantes', []))
                self.fields['agravantes'].initial = ", ".join(self.instance.circunstancias.get('agravantes', []))

            # --- INÍCIO DA MODIFICAÇÃO: Inicialização dos campos de punição sugerida ---
            if self.instance.punicao_sugerida:
                sugerida_str = self.instance.punicao_sugerida.lower()
                match = re.search(r'(\d+)\s+dias', sugerida_str)
                if match:
                    self.fields['punicao_sugerida_dias'].initial = int(match.group(1))
                
                if 'detenção' in sugerida_str:
                    self.fields['punicao_sugerida_tipo'].initial = 'detenção'
                elif 'prisão' in sugerida_str:
                    self.fields['punicao_sugerida_tipo'].initial = 'prisão'
                elif 'repreensão' in sugerida_str:
                    self.fields['punicao_sugerida_tipo'].initial = 'repreensão'
            # --- FIM DA MODIFICAÇÃO ---
            # --- INICIALIZAÇÃO DO CAMPO NUMÉRICO ---
            if self.instance.nova_punicao_dias:
                match = re.search(r'\((\d+)\)', self.instance.nova_punicao_dias)
                if match:
                    try:
                        self.fields['nova_punicao_dias_num'].initial = int(match.group(1))
                    except (ValueError, TypeError):
                        pass # Deixa vazio se não conseguir converter

        # --- INÍCIO DA MODIFICAÇÃO: Lógica para desabilitar campos ---
        # Se a instância existe e está em um dos status de finalização que permitem editar a punição
        if self.instance and self.instance.pk and self.instance.status in [
            'aguardando_publicacao'
        ]:
            # Define os únicos campos que devem permanecer editáveis
            editable_fields = {
                'nova_punicao_dias_num', 'nova_punicao_tipo', 
                'punicao_sugerida_dias', 'punicao_sugerida_tipo'
            }
            
            # Itera sobre todos os campos do formulário
            for field_name, field in self.fields.items():
                # Se o nome do campo não estiver na lista de campos editáveis
                if field_name not in editable_fields:
                    # Desabilita o campo
                    field.disabled = True
                    field.widget.attrs['title'] = 'Este campo não pode ser editado nesta fase do processo.'
        # --- FIM DA MODIFICAÇÃO ---


    def save(self, commit=True):
        # Pega a instância do modelo, mas não salva no banco ainda
        instance = super().save(commit=False)

        # Converte os campos de texto de volta para a estrutura JSON antes de salvar

        # Itens Enquadrados
        itens_text = self.cleaned_data.get('itens_enquadrados_text', '')
        itens_list = []
        for line in itens_text.splitlines():
            if ':' in line:
                parts = line.split(':', 1)
                numero_str = parts[0].strip()
                descricao = parts[1].strip()
                try:
                    # Tenta converter para int, mas permite continuar se falhar
                    numero = int(numero_str) if numero_str.isdigit() else numero_str
                    itens_list.append({'numero': numero, 'descricao': descricao})
                except ValueError:
                    # Adiciona mesmo se não for número, mas mantém a string
                    itens_list.append({'numero': numero_str, 'descricao': descricao})
        instance.itens_enquadrados = itens_list


        # Circunstâncias
        atenuantes = [item.strip() for item in self.cleaned_data.get('atenuantes', '').split(',') if item.strip()]
        agravantes = [item.strip() for item in self.cleaned_data.get('agravantes', '').split(',') if item.strip()]
        instance.circunstancias = {
            'atenuantes': atenuantes,
            'agravantes': agravantes
        }

        # --- INÍCIO DA MODIFICAÇÃO: Lógica para punição sugerida ---
        sugerida_dias = self.cleaned_data.get('punicao_sugerida_dias')
        sugerida_tipo = self.cleaned_data.get('punicao_sugerida_tipo')

        # Atualiza tanto a punição sugerida quanto a principal
        if sugerida_dias is not None and sugerida_tipo:
            dias_texto = num2words(sugerida_dias, lang='pt_BR')
            instance.punicao_sugerida = f"{sugerida_dias} dias de {sugerida_tipo}"
            instance.dias_punicao = f"{dias_texto} ({sugerida_dias:02d}) dias"
            instance.punicao = sugerida_tipo
            instance.justificado = False
        elif sugerida_tipo == 'repreensão':
            instance.punicao_sugerida = "repreensão"
            instance.dias_punicao = ""
            instance.punicao = sugerida_tipo
            instance.justificado = False
        else:
            instance.punicao_sugerida = "" # Limpa se os campos não forem válidos
            instance.dias_punicao = ""
            instance.punicao = ""

        # --- LÓGICA ATUALIZADA PARA PUNIÇÃO ---
        # Prioriza a Nova Punição se ela for preenchida
        nova_punicao_dias_num = self.cleaned_data.get('nova_punicao_dias_num')
        nova_punicao_tipo = self.cleaned_data.get('nova_punicao_tipo')

        if nova_punicao_dias_num is not None and nova_punicao_tipo:
            dias_texto = num2words(nova_punicao_dias_num, lang='pt_BR')
            instance.nova_punicao_dias = f"{dias_texto} ({nova_punicao_dias_num:02d}) dias"
            instance.nova_punicao_tipo = nova_punicao_tipo
            # Atualiza também a punição principal para refletir a nova decisão
            instance.dias_punicao = instance.nova_punicao_dias
            instance.punicao = instance.nova_punicao_tipo
            instance.justificado = False # Garante que não está justificado se definir punição
        elif nova_punicao_tipo == 'repreensão': # Caso específico de repreensão (sem dias)
             instance.nova_punicao_dias = ""
             instance.nova_punicao_tipo = nova_punicao_tipo
             instance.dias_punicao = ""
             instance.punicao = nova_punicao_tipo
             instance.justificado = False
        # Se a nova punição não foi preenchida, tenta usar a punição sugerida (IA)
        elif not instance.dias_punicao and not instance.punicao: # Só atualiza se a principal estiver vazia
            punicao_sugerida_str = self.cleaned_data.get('punicao_sugerida', '')
            match = re.search(r'(\d+)\s+dias\s+de\s+(.+)', punicao_sugerida_str, re.IGNORECASE)
            if match:
                dias_num = int(match.group(1))
                punicao_tipo = match.group(2).strip()
                dias_texto = num2words(dias_num, lang='pt_BR')
                instance.dias_punicao = f"{dias_texto} ({dias_num:02d}) dias"
                instance.punicao = punicao_tipo
            else:
                instance.dias_punicao = ""
                instance.punicao = punicao_sugerida_str # Assume que é repreensão ou justificado
            # Não mexe em nova_punicao_dias/tipo aqui

        # --- FIM DA LÓGICA ATUALIZADA ---

        # Chama os métodos do modelo para recalcular tudo antes de salvar
        instance.definir_natureza_transgressao() # Baseado em instance.punicao agora
        instance.calcular_e_atualizar_comportamento() # Baseado em instance.punicao agora

        if commit:
            instance.save()
        return instance