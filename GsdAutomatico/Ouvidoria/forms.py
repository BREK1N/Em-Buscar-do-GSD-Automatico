from django import forms
from .models import Militar, PATD
import json

class AtribuirOficialForm(forms.ModelForm):
    class Meta:
        model = PATD
        fields = ['oficial_responsavel']
        labels = {
            'oficial_responsavel': 'Selecione o Oficial para Atribuir'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['oficial_responsavel'].queryset = Militar.objects.filter(oficial=True).order_by('posto', 'nome_guerra')
        self.fields['oficial_responsavel'].empty_label = "--- Selecione um Oficial ---"

class AceitarAtribuicaoForm(forms.Form):
    senha = forms.CharField(widget=forms.PasswordInput, label="Sua Senha de Acesso")

class MilitarForm(forms.ModelForm):
    # Formulário para criar e atualizar registros de Militares.
    class Meta:
        model = Militar
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

    class Meta:
        model = PATD
        fields = [
            'transgressao', 'oficial_responsavel', 'testemunha1', 'testemunha2', 
            'data_ocorrencia', 'itens_enquadrados_text', 'atenuantes', 'agravantes', 'punicao_sugerida',
            'comprovante', 'dias_punicao', 'punicao', 'transgressao_afirmativa', 'natureza_transgressao', 'comportamento',
            'alegacao_defesa_resumo'
        ]
        
        widgets = {
            'transgressao': forms.Textarea(attrs={'rows': 4}),
            'data_ocorrencia': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'punicao_sugerida': forms.Textarea(attrs={'rows': 3}),
            'comprovante': forms.Textarea(attrs={'rows': 3}),
            'transgressao_afirmativa': forms.Textarea(attrs={'rows': 3}),
            'alegacao_defesa_resumo': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'transgressao': "Descrição da Transgressão",
            'oficial_responsavel': "Oficial Responsável",
            'testemunha1': "1ª Testemunha",
            'testemunha2': "2ª Testemunha",
            'data_ocorrencia': "Data da Ocorrência",
            'punicao_sugerida': "Punição Sugerida pela IA",
            'comprovante': "Comprovante da Transgressão",
            'dias_punicao': "Dias de Punição",
            'punicao': "Punição",
            'transgressao_afirmativa': "Transgressão Afirmativa",
            'natureza_transgressao': "Natureza da Transgressão",
            'comportamento': "Comportamento",
            'alegacao_defesa_resumo': "Resumo da Alegação de Defesa",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra a lista de militares para testemunhas
        queryset_testemunhas = Militar.objects.filter(subsetor='OUVIDORIA')
        self.fields['testemunha1'].queryset = queryset_testemunhas
        self.fields['testemunha2'].queryset = queryset_testemunhas

        # Preenche os campos de texto com os dados JSON formatados
        if self.instance and self.instance.pk:
            if self.instance.itens_enquadrados:
                itens_str = "\n".join([f"{item.get('numero', '')}: {item.get('descricao', '')}" for item in self.instance.itens_enquadrados])
                self.fields['itens_enquadrados_text'].initial = itens_str
            
            if self.instance.circunstancias:
                self.fields['atenuantes'].initial = ", ".join(self.instance.circunstancias.get('atenuantes', []))
                self.fields['agravantes'].initial = ", ".join(self.instance.circunstancias.get('agravantes', []))

    def save(self, commit=True):
        # Converte os campos de texto de volta para a estrutura JSON antes de salvar
        
        # Itens Enquadrados
        itens_text = self.cleaned_data.get('itens_enquadrados_text', '')
        itens_list = []
        for line in itens_text.splitlines():
            if ':' in line:
                numero, descricao = line.split(':', 1)
                try:
                    itens_list.append({'numero': int(numero.strip()), 'descricao': descricao.strip()})
                except ValueError:
                    # Ignora linhas mal formatadas
                    pass
        self.instance.itens_enquadrados = itens_list

        # Circunstâncias
        atenuantes = [item.strip() for item in self.cleaned_data.get('atenuantes', '').split(',') if item.strip()]
        agravantes = [item.strip() for item in self.cleaned_data.get('agravantes', '').split(',') if item.strip()]
        self.instance.circunstancias = {
            'atenuantes': atenuantes,
            'agravantes': agravantes
        }
            
        return super().save(commit=commit)

