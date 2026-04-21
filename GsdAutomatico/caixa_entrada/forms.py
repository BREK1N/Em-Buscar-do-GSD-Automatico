from django import forms
from django.contrib.auth import get_user_model
from Secao_pessoal.models import Efetivo
from .models import Notificacao, Mensagem

User = get_user_model()


class NotificacaoForm(forms.ModelForm):
    class Meta:
        model = Notificacao
        fields = ['destinatario', 'titulo', 'mensagem']
        widgets = {
            'destinatario': forms.Select(attrs={'class': 'form-select select2'}),
            'titulo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Assunto do aviso'}),
            'mensagem': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Digite a mensagem...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        efetivos_ids = User.objects.filter(
            is_active=True, profile__militar__isnull=False
        ).values_list('profile__militar__id', flat=True)
        self.fields['destinatario'].queryset = Efetivo.objects.filter(
            id__in=efetivos_ids
        ).order_by('setor', 'nome_guerra')


class MensagemForm(forms.ModelForm):
    destinatarios = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select destinatarios-select'}),
        label="Destinatários",
        required=True,
    )
    cc = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select cc-select'}),
        label="CC (Com cópia)",
        required=False,
    )

    class Meta:
        model = Mensagem
        fields = ['destinatarios', 'cc', 'assunto', 'corpo', 'tipo']
        widgets = {
            'assunto': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Assunto da mensagem',
            }),
            'corpo': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Escreva sua mensagem aqui...',
            }),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        qs = User.objects.filter(is_active=True).order_by('first_name', 'username')
        self.fields['destinatarios'].queryset = qs
        self.fields['destinatarios'].label_from_instance = self._label_user
        self.fields['cc'].queryset = qs
        self.fields['cc'].label_from_instance = self._label_user

    @staticmethod
    def _label_user(user):
        try:
            mil = user.profile.militar
            return f"{mil.posto} {mil.nome_guerra} ({mil.setor or 'sem setor'})"
        except Exception:
            return user.get_full_name() or user.username


class FiltroInboxForm(forms.Form):
    TIPO_CHOICES = [('', 'Todos'), ('mensagem', 'Mensagem'), ('chamado', 'Chamado')]
    STATUS_CHOICES = [
        ('', 'Todos'),
        ('aberto', 'Aberto'),
        ('em_andamento', 'Em Andamento'),
        ('resolvido', 'Resolvido'),
    ]

    tipo = forms.ChoiceField(
        choices=TIPO_CHOICES, required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    status_chamado = forms.ChoiceField(
        choices=STATUS_CHOICES, required=False,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    data_inicial = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )
    data_final = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control form-control-sm', 'type': 'date'})
    )
    q = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-sm',
            'placeholder': 'Buscar por assunto...',
        })
    )
