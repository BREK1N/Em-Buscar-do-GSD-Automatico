from django import forms
from .models import Militar, PATD

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
    Formulário para editar uma PATD existente.
    """
    class Meta:
        model = PATD
        # CAMPOS DE TESTEMUNHA ADICIONADOS
        fields = ['transgressao', 'oficial_responsavel', 'testemunha1', 'testemunha2', 'data_ocorrencia']
        
        widgets = {
            'transgressao': forms.Textarea(attrs={'rows': 4}),
            'data_ocorrencia': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date', 'class': 'form-control'}
            ),
        }
        labels = {
            'transgressao': "Descrição da Transgressão",
            'oficial_responsavel': "Oficial Responsável",
            'testemunha1': "1ª Testemunha",
            'testemunha2': "2ª Testemunha",
            'data_ocorrencia': "Data da Ocorrência",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # FILTRA A LISTA DE MILITARES PARA TESTEMUNHAS
        queryset_testemunhas = Militar.objects.filter(subsetor='OUVIDORIA')
        self.fields['testemunha1'].queryset = queryset_testemunhas
        self.fields['testemunha2'].queryset = queryset_testemunhas
