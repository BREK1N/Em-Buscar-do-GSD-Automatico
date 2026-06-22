from django import forms
from Secao_pessoal.models import Efetivo, Posto, Quad, Especializacao, OM, Setor, Subsetor, LotacaoPessoal
from django.contrib.auth import get_user_model

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
            'posto', 'quad', 'especializacao', 'saram', 'nome_completo', 'nome_guerra',
            'turma', 'situacao', 'om', 'setor', 'subsetor', 'oficial', 'observacao',
            'assinatura', 'unidade_prestacao_servico', 'data_inicio_prestacao',
            'data_vencimento_prestacao', 'portaria_prestacao', 'data_portaria_prestacao',
            'boletim_prestacao', 'data_boletim_prestacao',
            'data_desligamento', 'motivo_desligamento', 'documento_desligamento', 'funcao_desligamento',
            'identidade_civil', 'identidade_aer', 'cpf', 'data_nascimento', 'nome_mae', 'nome_pai',
            'conjuge', 'ano_praca', 'contato_1', 'contato_2', 'contato_3', 'contato_4',
            'email_1', 'email_2', 'email_3', 'cep', 'endereco', 'complemento', 'bairro',
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
            'observacao': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Observações sobre a situação do militar (ex: motivo da baixa, período de férias).'}),
            'assinatura': forms.HiddenInput(),
            'unidade_prestacao_servico': forms.TextInput(attrs={'placeholder': 'Ex: BAGL'}),
            'portaria_prestacao': forms.TextInput(attrs={'placeholder': 'Ex: Portaria Nº 123'}),
            'boletim_prestacao': forms.TextInput(attrs={'placeholder': 'Ex: BCA Nº 45'}),
            'data_inicio_prestacao': forms.DateInput(attrs={'type': 'date'}),
            'data_vencimento_prestacao': forms.DateInput(attrs={'type': 'date'}),
            'data_portaria_prestacao': forms.DateInput(attrs={'type': 'date'}),
            'data_boletim_prestacao': forms.DateInput(attrs={'type': 'date'}),
            'data_desligamento': forms.DateInput(attrs={'type': 'date'}),
            'motivo_desligamento': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Motivo do desligamento'}),
            'documento_desligamento': forms.TextInput(attrs={'placeholder': 'Ex: Bol O nº 123 de 01/01/2026'}),
            'funcao_desligamento': forms.TextInput(attrs={'placeholder': 'Função conforme publicado'}),
            'data_nascimento': forms.DateInput(attrs={'type': 'date'}),
            'cpf': forms.TextInput(attrs={'placeholder': '000.000.000-00'}),
            'identidade_civil': forms.TextInput(attrs={'placeholder': 'Identidade Civil'}),
            'identidade_aer': forms.TextInput(attrs={'placeholder': 'Identidade Aeronáutica'}),
            'nome_mae': forms.TextInput(attrs={'placeholder': 'Nome da mãe'}),
            'nome_pai': forms.TextInput(attrs={'placeholder': 'Nome do pai'}),
            'conjuge': forms.TextInput(attrs={'placeholder': 'Nome do(a) cônjuge'}),
            'ano_praca': forms.TextInput(attrs={'placeholder': 'Ex: 2024'}),
            'contato_1': forms.TextInput(attrs={'placeholder': '(00) 00000-0000'}),
            'contato_2': forms.TextInput(attrs={'placeholder': '(00) 00000-0000'}),
            'contato_3': forms.TextInput(attrs={'placeholder': '(00) 00000-0000'}),
            'contato_4': forms.TextInput(attrs={'placeholder': '(00) 00000-0000'}),
            'email_1': forms.EmailInput(attrs={'placeholder': 'email@exemplo.com'}),
            'email_2': forms.EmailInput(attrs={'placeholder': 'email@exemplo.com'}),
            'email_3': forms.EmailInput(attrs={'placeholder': 'email@exemplo.com'}),
            'cep': forms.TextInput(attrs={'placeholder': '00000-000'}),
            'endereco': forms.TextInput(attrs={'placeholder': 'Endereço'}),
            'complemento': forms.TextInput(attrs={'placeholder': 'Complemento'}),
            'bairro': forms.TextInput(attrs={'placeholder': 'Bairro'}),
        }

    # Definindo os campos como ChoiceField para forçar o uso de <select>
    posto = forms.ChoiceField(required=False)
    quad = forms.ChoiceField(required=False)
    especializacao = forms.ChoiceField(required=False)
    om = forms.ChoiceField(required=False)
    setor = forms.ChoiceField(required=False)
    subsetor = forms.ChoiceField(required=False)


class LotacaoPessoalForm(forms.ModelForm):
    # Formulário para cadastrar/editar vagas previstas (TLP) por posto/quadro/especialidade/OM.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        opcoes_posto = [(p.nome, p.nome) for p in Posto.objects.all()]
        opcoes_quad = [(q.nome, q.nome) for q in Quad.objects.all()]
        opcoes_especializacao = [(e.nome, e.nome) for e in Especializacao.objects.all()]
        opcoes_om = [(o.nome, o.nome) for o in OM.objects.all()]

        self.fields['posto'].choices = [('', '---------')] + opcoes_posto
        self.fields['quad'].choices = [('', '---------')] + opcoes_quad
        self.fields['especializacao'].choices = [('', '---------')] + opcoes_especializacao
        self.fields['om'].choices = [('', '---------')] + opcoes_om

    class Meta:
        model = LotacaoPessoal
        fields = ['posto', 'quad', 'especializacao', 'om', 'vagas_previstas']
        widgets = {
            'posto': forms.Select(),
            'quad': forms.Select(),
            'especializacao': forms.Select(),
            'om': forms.Select(),
            'vagas_previstas': forms.NumberInput(attrs={'min': 0, 'placeholder': 'Quantidade de vagas previstas'}),
        }

    posto = forms.ChoiceField(required=False)
    quad = forms.ChoiceField(required=False)
    especializacao = forms.ChoiceField(required=False)
    om = forms.ChoiceField(required=False)
