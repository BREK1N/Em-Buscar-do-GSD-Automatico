from django import forms
from .models import Militar, PATD
import json

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
    # Usando CharField com Textarea para facilitar a edição de dados JSON
    itens_enquadrados_text = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5}),
        required=False,
        label="Itens Enquadrados (JSON)",
        help_text="Edite os itens em formato JSON. Ex: [{'numero': 1, 'descricao': '...'}]"
    )
    circunstancias_text = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5}),
        required=False,
        label="Circunstâncias (JSON)",
        help_text="Edite as circunstâncias em formato JSON. Ex: {'agravantes': ['a'], 'atenuantes': []}"
    )

    class Meta:
        model = PATD
        fields = [
            'transgressao', 'oficial_responsavel', 'testemunha1', 'testemunha2', 
            'data_ocorrencia', 'punicao_sugerida'
        ]
        
        widgets = {
            'transgressao': forms.Textarea(attrs={'rows': 4}),
            'data_ocorrencia': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': 'form-control'}
            ),
            'punicao_sugerida': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'transgressao': "Descrição da Transgressão",
            'oficial_responsavel': "Oficial Responsável",
            'testemunha1': "1ª Testemunha",
            'testemunha2': "2ª Testemunha",
            'data_ocorrencia': "Data da Ocorrência",
            'punicao_sugerida': "Punição Sugerida pela IA",
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
                self.fields['itens_enquadrados_text'].initial = json.dumps(self.instance.itens_enquadrados, indent=2, ensure_ascii=False)
            if self.instance.circunstancias:
                self.fields['circunstancias_text'].initial = json.dumps(self.instance.circunstancias, indent=2, ensure_ascii=False)

    def save(self, commit=True):
        # Converte o texto de volta para JSON antes de salvar
        try:
            self.instance.itens_enquadrados = json.loads(self.cleaned_data['itens_enquadrados_text'])
        except (json.JSONDecodeError, TypeError):
            # Se o texto for inválido, mantém o valor original ou define como nulo
            if not self.instance.pk: self.instance.itens_enquadrados = None
        
        try:
            self.instance.circunstancias = json.loads(self.cleaned_data['circunstancias_text'])
        except (json.JSONDecodeError, TypeError):
            if not self.instance.pk: self.instance.circunstancias = None
            
        return super().save(commit=commit)