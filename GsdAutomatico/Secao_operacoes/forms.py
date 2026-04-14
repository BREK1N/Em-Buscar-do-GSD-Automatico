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
        fields = ['nome', 'descricao', 'militares']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PostoEscalaForm(forms.ModelForm):
    class Meta:
        model = PostoEscala
        fields = ['nome']
        widgets = {
            'nome': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex: Guarita 1, Parabala, Pedestre...',
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
        super().__init__(*args, **kwargs)
        if escala_id:
            try:
                escala = Escala.objects.get(id=escala_id)
                self.fields['militar'].queryset = escala.militares.all().order_by('nome_guerra')
                postos_qs = escala.postos.all()
                if postos_qs.exists():
                    self.fields['posto'].queryset = postos_qs
                    self.fields['posto'].required = False
                    self.fields['posto'].empty_label = "— Sem posto específico —"
                else:
                    # Sem postos cadastrados: esconde o campo
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

        if militar and data and self.escala_id_val:
            # Regra 1: não pode ser escalado para 2 serviços no mesmo dia
            if TurnoEscala.objects.filter(militar=militar, data=data).exists():
                self.add_error('data', 'Este militar já está escalado para um serviço neste dia.')

            # Regra 2: saindo de serviço (trabalhou dia anterior)
            if TurnoEscala.objects.filter(militar=militar, data=data - timedelta(days=1)).exists():
                self.add_error('data', 'O militar está saindo de serviço neste dia (trabalha no dia anterior).')

            # Regra 3: entrará de serviço no dia seguinte
            if TurnoEscala.objects.filter(militar=militar, data=data + timedelta(days=1)).exists():
                self.add_error('data', 'O militar entrará de serviço no dia seguinte — precisa de descanso.')

            # Regra 4: duplicata na mesma escala e data
            if TurnoEscala.objects.filter(militar=militar, escala_id=self.escala_id_val, data=data).exists():
                self.add_error('militar', 'Este militar já está escalado para esta escala neste dia.')

        return cleaned_data
