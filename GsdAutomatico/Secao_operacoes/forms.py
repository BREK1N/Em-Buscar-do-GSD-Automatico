from django import forms
from .models import Escala, TurnoEscala
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

class TurnoEscalaForm(forms.ModelForm):
    class Meta:
        model = TurnoEscala
        fields = ['militar', 'data', 'observacao']
        widgets = {
            'militar': forms.Select(attrs={'class': 'form-select'}),
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
                
            # Regra 2: não pode ser escalado saindo de serviço (dia seguinte ou dia anterior ao de um serviço)
            # Saindo de serviço significa que trabalhou no dia anterior e não pode trabalhar hoje.
            # Ou se trabalhou hoje, não pode trabalhar amanhã (então se eu tento agendar amanhã, e tem hoje, dá erro).
            if TurnoEscala.objects.filter(militar=militar, data=data - timedelta(days=1)).exists():
                self.add_error('data', 'O militar está saindo de serviço neste dia (trabalha no dia anterior).')
            
            if TurnoEscala.objects.filter(militar=militar, data=data + timedelta(days=1)).exists():
                self.add_error('data', 'O militar entrará de serviço no dia seguinte, não podendo ser escalado hoje para não ficar sem descanso.')

            # Regra 3: não pode ser escalado para o mesmo serviço 2 vezes (na mesma escala e data).
            # Se for para o mesmo dia e mesma escala, a Regra 1 já pegou, mas pra garantir:
            if TurnoEscala.objects.filter(militar=militar, escala_id=self.escala_id_val, data=data).exists():
                self.add_error('militar', 'Este militar já está escalado para esta escala neste dia.')
                
        return cleaned_data
