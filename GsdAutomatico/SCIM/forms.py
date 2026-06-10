from django import forms
from .models import TipoCurso, CursoEfetivo


class TipoCursoForm(forms.ModelForm):
    class Meta:
        model = TipoCurso
        fields = ['nome', 'descricao', 'ativo']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: Curso de Choque, PQD...'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'ativo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CursoEfetivoForm(forms.ModelForm):
    class Meta:
        model = CursoEfetivo
        fields = ['efetivo', 'tipo_curso', 'data_realizacao', 'instituicao', 'certificado', 'observacoes']
        widgets = {
            'efetivo': forms.Select(attrs={'class': 'form-select', 'id': 'id_efetivo'}),
            'tipo_curso': forms.Select(attrs={'class': 'form-select'}),
            'data_realizacao': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'instituicao': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex: BOPE, CFP, CFAP...'}),
            'certificado': forms.FileInput(attrs={'class': 'form-control'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo_curso'].queryset = TipoCurso.objects.filter(ativo=True)
