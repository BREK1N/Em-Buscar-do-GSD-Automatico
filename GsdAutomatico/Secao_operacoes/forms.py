from django import forms
from .models import Escala, TurnoEscala, PostoEscala
from Secao_pessoal.models import Efetivo


class EscalaForm(forms.ModelForm):
    militares = forms.ModelMultipleChoiceField(
        queryset=Efetivo.objects.all().order_by('nome_guerra'),
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': '10'}),
        required=False,
        label="Militares Vinculados a esta Escala"
    )

    class Meta:
        model = Escala
        fields = ['nome', 'descricao', 'tipo', 'duracao_horas', 'militares']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'duracao_horas': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 12, 24, 48...',
                'min': '1',
            }),
        }


class PostoEscalaForm(forms.ModelForm):
    class Meta:
        model = PostoEscala
        fields = ['nome', 'horario']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Guarita 1, Parabala, Pedestre...',
                'autocomplete': 'off',
            }),
            'horario': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: 0h às 6h, 6h às 12h, Manhã...',
                'autocomplete': 'off',
            }),
        }


class TurnoEscalaForm(forms.ModelForm):
    class Meta:
        model = TurnoEscala
        fields = ['militar', 'posto', 'data', 'observacao']
        widgets = {
            'militar': forms.Select(attrs={'class': 'form-select'}),
            'posto': forms.Select(attrs={'class': 'form-select'}),
            'data': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'observacao': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        escala_id = kwargs.pop('escala_id', None)
        self.escala_id_val = escala_id
        self.escala_tipo = None
        super().__init__(*args, **kwargs)
        if escala_id:
            try:
                escala = Escala.objects.get(id=escala_id)
                self.escala_tipo = escala.tipo
                self.fields['militar'].queryset = escala.militares.all().order_by('nome_guerra')
                postos_qs = escala.postos.all()
                if postos_qs.exists():
                    self.fields['posto'].queryset = postos_qs
                    self.fields['posto'].required = True
                    self.fields['posto'].empty_label = None  # sem opção "sem posto"
                else:
                    self.fields['posto'].queryset = PostoEscala.objects.none()
                    self.fields['posto'].required = False
                    self.fields['posto'].widget = forms.HiddenInput()
            except Escala.DoesNotExist:
                pass

    def clean(self):
        from datetime import timedelta
        cleaned_data = super().clean()
        militar = cleaned_data.get('militar')
        data = cleaned_data.get('data')
        posto = cleaned_data.get('posto')

        if militar and data and self.escala_id_val:
            tipo = self.escala_tipo or '24h'

            # Regra global: posto já ocupado por outro militar no mesmo dia
            if posto and TurnoEscala.objects.filter(posto=posto, data=data).exclude(militar=militar).exists():
                self.add_error('posto', f'O posto "{posto.nome}" já está ocupado por outro militar neste dia.')

            if tipo == 'turno':
                # For turno type: only block same military + same posto + same day
                qs = TurnoEscala.objects.filter(militar=militar, data=data)
                if posto:
                    qs = qs.filter(posto=posto)
                if qs.exists():
                    self.add_error('data', 'Este militar já está escalado para este posto neste dia.')
            else:
                # For 24h, permanencia, sbv: apply full conflict rules
                if TurnoEscala.objects.filter(militar=militar, data=data).exists():
                    self.add_error('data', 'Este militar já está escalado para um serviço neste dia.')

                if tipo == '24h':
                    if TurnoEscala.objects.filter(militar=militar, data=data - timedelta(days=1)).exists():
                        self.add_error('data', 'O militar está saindo de serviço neste dia (trabalha no dia anterior).')
                    if TurnoEscala.objects.filter(militar=militar, data=data + timedelta(days=1)).exists():
                        self.add_error('data', 'O militar entrará de serviço no dia seguinte — precisa de descanso.')

            # Always block exact same escala + military + day duplicate
            if TurnoEscala.objects.filter(militar=militar, escala_id=self.escala_id_val, data=data).exists():
                if not (tipo == 'turno' and posto):
                    self.add_error('militar', 'Este militar já está escalado para esta escala neste dia.')

        return cleaned_data
