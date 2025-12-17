from django import forms
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from django.contrib.auth.models import User, Group
from Secao_pessoal.models import Efetivo
from .models import UserProfile

class CustomUserCreationForm(UserCreationForm):
    militar = forms.ModelChoiceField(
        queryset=Efetivo.objects.all(),
        required=False,
        label="Militar Associado",
        help_text="Associe este utilizador a um militar existente no efetivo (opcional).",
        widget=forms.HiddenInput()
    )
    
    grupos = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Permissões de Aplicação",
        help_text="Selecione os aplicativos que este utilizador poderá aceder."
    )

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            if 'grupos' in self.cleaned_data:
                user.groups.set(self.cleaned_data['grupos'])
            
            militar_selecionado = self.cleaned_data.get('militar')
            
            profile, created = UserProfile.objects.get_or_create(user=user)
            if militar_selecionado:
                profile.militar = militar_selecionado
                profile.save()
        return user


# --- NOVO CÓDIGO ADICIONADO ABAIXO ---

class CustomSetPasswordForm(SetPasswordForm):
    """
    Formulário para alteração de senha que não permite usar '12345678'.
    """
    def clean_new_password1(self):
        password = self.cleaned_data.get('new_password1')
        if password == '12345678':
            raise forms.ValidationError(
                "Esta senha não é permitida. Por favor, escolha uma senha diferente."
            )
        return password