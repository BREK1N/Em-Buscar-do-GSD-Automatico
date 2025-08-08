from django import forms
from .models import Militar, PATD

class MilitarForm(forms.ModelForm):
    #Formulário para criar e atualizar registros de Militares.
    class Meta:
        model = Militar
        # Inclui todos os campos do modelo no formulário
        fields = '__all__'
        # Adiciona classes CSS para estilização e placeholders para melhor UX
        widgets = {
            'nome_completo': forms.TextInput(attrs={'placeholder': 'Nome completo do militar'}),
            'nome_guerra': forms.TextInput(attrs={'placeholder': 'Nome de guerra'}),
            'saram': forms.NumberInput(attrs={'placeholder': 'Apenas números'}),
            'telefone': forms.NumberInput(attrs={'placeholder': 'DDD + Número'}),
            'turma': forms.TextInput(attrs={'placeholder': 'Ex: 2024'}),
            'posto': forms.TextInput(attrs={'placeholder': 'Ex: Capitão'}),
            'graduacao': forms.TextInput(attrs={'placeholder': 'Ex: Sargento'}),
            'secao_om': forms.TextInput(attrs={'placeholder': 'Ex: 1ª Seção'}),
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
