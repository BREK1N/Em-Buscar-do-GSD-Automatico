from django import forms
from Secao_pessoal.models import Efetivo, Posto, Quad, Especializacao, OM, Setor, Subsetor
from .models import Notificacao, Efetivo

class MilitarForm(forms.ModelForm):
    # Formulário para criar e atualizar registros de Militares.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Opções para os campos de escolha
        opcoes_posto = [(p.nome, p.nome) for p in Posto.objects.all()]
        opcoes_quad = [(q.nome, q.nome) for q in Quad.objects.all()]
        opcoes_especializacao = [(e.nome, e.nome) for e in Especializacao.objects.all()]
        opcoes_om = [(o.nome, o.nome) for o in OM.objects.all()]
        opcoes_setor = [(s.nome, s.nome) for s in Setor.objects.all()]
        opcoes_subsetor = [(ss.nome, ss.nome) for ss in Subsetor.objects.all()]

        # Adiciona uma opção em branco no início
        self.fields['posto'].choices = [('', '---------')] + opcoes_posto
        self.fields['quad'].choices = [('', '---------')] + opcoes_quad
        self.fields['especializacao'].choices = [('', '---------')] + opcoes_especializacao
        self.fields['om'].choices = [('', '---------')] + opcoes_om
        self.fields['setor'].choices = [('', '---------')] + opcoes_setor
        self.fields['subsetor'].choices = [('', '---------')] + opcoes_subsetor

    class Meta:
        model = Efetivo
        fields = [
            'posto', 'quad', 'especializacao', 'saram', 'nome_completo',
            'nome_guerra', 'turma', 'situacao', 'om', 'setor', 'subsetor', 'oficial',
            'assinatura' # Campo adicionado para futuras implementações
        ]
        
        # Usando Select para os campos que agora são listas
        widgets = {
            'posto': forms.Select(),
            'quad': forms.Select(),
            'especializacao': forms.Select(),
            'om': forms.Select(),
            'setor': forms.Select(),
            'subsetor': forms.Select(),
            
            # Widgets que permanecem os mesmos
            'saram': forms.NumberInput(attrs={'placeholder': 'Apenas números'}),
            'nome_completo': forms.TextInput(attrs={'placeholder': 'Nome completo do militar'}),
            'nome_guerra': forms.TextInput(attrs={'placeholder': 'Nome de guerra'}),
            'turma': forms.TextInput(attrs={'placeholder': 'Ex: 2024'}),
            'situacao': forms.TextInput(attrs={'placeholder': 'Ex: Ativo'}),
            'assinatura': forms.HiddenInput(),
        }

    # Definindo os campos como ChoiceField para forçar o uso de <select>
    posto = forms.ChoiceField(required=False)
    quad = forms.ChoiceField(required=False)
    especializacao = forms.ChoiceField(required=False)
    om = forms.ChoiceField(required=False)
    setor = forms.ChoiceField(required=False)
    subsetor = forms.ChoiceField(required=False)

    # Adicione isso em Secao_pessoal/forms.py
class NotificacaoForm(forms.ModelForm):
    class Meta:
        model = Notificacao
        fields = ['destinatario', 'titulo', 'mensagem']
        widgets = {
            'destinatario': forms.Select(attrs={'class': 'form-select select2'}), # select2 se tiver, senão form-select
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Assunto do aviso'}),
            'mensagem': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Digite a mensagem...'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Agrupa os destinatários por setor
        efetivos = Efetivo.objects.all().order_by('setor', 'nome_guerra')
        self.fields['destinatario'].queryset = efetivos
        
        choices_grouped = {}
        for militar in efetivos:
            setor = militar.setor if militar.setor else "Outros"
            if setor not in choices_grouped:
                choices_grouped[setor] = []
            choices_grouped[setor].append((militar.id, f"{militar.posto} {militar.nome_guerra}"))
            
        choices = [('', '---------')] + [(setor, choices_grouped[setor]) for setor in sorted(choices_grouped.keys())]
        self.fields['destinatario'].choices = choices
