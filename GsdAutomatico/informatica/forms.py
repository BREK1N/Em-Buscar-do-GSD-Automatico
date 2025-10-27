# GsdAutomatico/informatica/forms.py

from django import forms
# Importa o modelo Militar do app Ouvidoria
from Ouvidoria.models import Militar

class MilitarForm(forms.ModelForm):
    """
    Formulário para criar e atualizar Militares dentro do app Informatica.
    """
    class Meta:
        model = Militar
        # Inclui os campos relevantes para administração
        fields = [
            'posto', 'quad', 'especializacao', 'saram', 'nome_completo',
            'nome_guerra', 'turma', 'situacao', 'om', 'setor', 'subsetor', 'oficial',
            # 'assinatura' e 'senha_unica' podem ser omitidos aqui ou gerenciados separadamente
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
            # 'assinatura': forms.HiddenInput(), # Se não for gerenciar aqui
        }
        # Adicionar labels se necessário (opcional, Django usa os verbose_name do modelo)
        labels = {
            'saram': 'SARAM',
            'om': 'OM',
            'quad': 'Quadro',
        }