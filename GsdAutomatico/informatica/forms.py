# GsdAutomatico/informatica/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User, Group
# Importa os modelos de outros apps
from Ouvidoria.models import Configuracao
from Secao_pessoal.models import Efetivo
from login.models import UserProfile # Modelo do Login


class InformaticaUserCreationForm(forms.ModelForm):
    """ Formulário para criar novos utilizadores na área de informática """

    first_name = forms.CharField(
        required=False, label="Primeiro Nome",
        widget=forms.TextInput(attrs={'placeholder': 'Preenchido automaticamente ao vincular militar'})
    )
    last_name = forms.CharField(
        required=False, label="Último Nome",
        widget=forms.TextInput(attrs={'placeholder': 'Preenchido automaticamente ao vincular militar'})
    )
    email = forms.EmailField(
        required=False, label="E-mail",
        widget=forms.EmailInput(attrs={'placeholder': 'email@exemplo.com'})
    )
    militar = forms.ModelChoiceField(
        queryset=Efetivo.objects.all(),
        required=False,
        label="Militar Associado (Opcional)",
        help_text="Associe este utilizador a um militar existente no efetivo.",
        widget=forms.HiddenInput()
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Grupos de Permissão",
        help_text="Os grupos que este utilizador pertence."
    )

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "militar", "groups")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password('12345678')
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name  = self.cleaned_data.get('last_name', '')
        user.email      = self.cleaned_data.get('email', '')

        # Se nenhum nome foi preenchido manualmente, puxar do militar vinculado
        militar_selecionado = self.cleaned_data.get('militar')
        if militar_selecionado and not user.first_name and not user.last_name:
            partes = (militar_selecionado.nome_completo or '').split()
            user.first_name = partes[0] if partes else ''
            user.last_name  = partes[-1] if len(partes) > 1 else ''

        if commit:
            user.save()
            self.save_m2m()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            if militar_selecionado:
                profile.militar = militar_selecionado
                profile.save()
        return user


class InformaticaUserChangeForm(UserChangeForm):
    """ Formulário para editar utilizadores existentes """
    password = None # Remove o campo de senha da edição

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Grupos de Permissão",
        help_text="Os grupos que este utilizador pertence."
    )

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser', 'groups')


class GroupForm(forms.ModelForm):
    """ Formulário para Grupos de Permissão """
    class Meta:
        model = Group
        fields = ('name', 'permissions')
        widgets = {
            'permissions': forms.CheckboxSelectMultiple,
        }

class UserProfileForm(forms.ModelForm):
    """ Formulário para editar UserProfile (associar militar) """
    class Meta:
        model = UserProfile
        fields = ('militar',)


class ConfiguracaoForm(forms.ModelForm):
    """ Formulário para gerenciar as Configurações Gerais """
    class Meta:
        model = Configuracao
        fields = ('comandante_gsd', 'comandante_bagl', 'prazo_defesa_dias', 'prazo_defesa_minutos')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filtra os selects para mostrar apenas oficiais
        self.fields['comandante_gsd'].queryset = Efetivo.objects.filter(oficial=True).order_by('posto', 'nome_guerra')
        self.fields['comandante_gsd'].empty_label = "--- Selecione ---"
        self.fields['comandante_bagl'].queryset = Efetivo.objects.filter(oficial=True).order_by('posto', 'nome_guerra')
        self.fields['comandante_bagl'].empty_label = "--- Selecione ---"
