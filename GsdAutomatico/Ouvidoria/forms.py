from django import forms
from .models import Militar, PATD

class MilitarForm(forms.ModelForm):
    #Formulário para criar e atualizar registros de Militares.
    class Meta:
        model = Militar
        # Inclui todos os campos do modelo no formulário
        fields = [
            'posto', 'quad', 'especializacao', 'saram', 'nome_completo', 
            'nome_guerra', 'turma', 'situacao', 'om', 'setor', 'subsetor', 'oficial'
        ]
        # Adiciona classes CSS para estilização e placeholders para melhor UX
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
        }

class PATDForm(forms.ModelForm):
    """
    Formulário para editar uma PATD existente.
    """
    data_termino = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        required=False
    )

    class Meta:
        model = PATD
        fields = ['transgressao', 'oficial_responsavel', 'data_termino']