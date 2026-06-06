# GsdAutomatico/informatica/forms.py

import secrets

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User, Group
# Importa os modelos de outros apps
from Ouvidoria.models import Configuracao
from Secao_pessoal.models import Efetivo
from login.models import UserProfile # Modelo do Login


class InformaticaUserCreationForm(forms.ModelForm):
    """ Formulário para criar novos utilizadores na área de informática """

    nome_completo = forms.CharField(
        required=False, label="Nome Completo",
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
    )

    class Meta:
        model = User
        fields = ("username", "email", "militar", "groups")

    def save(self, commit=True):
        user = super().save(commit=False)
        temp_password = secrets.token_urlsafe(10)
        user.set_password(temp_password)
        user._generated_password = temp_password  # lido pela view para exibir uma única vez
        user.email = self.cleaned_data.get('email', '')

        nome = self.cleaned_data.get('nome_completo', '').strip()
        militar_selecionado = self.cleaned_data.get('militar')
        if not nome and militar_selecionado:
            nome = (militar_selecionado.nome_completo or '').strip()
        partes = nome.split()
        user.first_name = partes[0] if partes else ''
        user.last_name  = ' '.join(partes[1:]) if len(partes) > 1 else ''

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
    password = None

    nome_completo = forms.CharField(
        required=False, label="Nome Completo",
        widget=forms.TextInput(attrs={'placeholder': 'Nome completo do utilizador'})
    )
    militar = forms.ModelChoiceField(
        queryset=Efetivo.objects.all(),
        required=False,
        label="Militar Associado",
        widget=forms.HiddenInput()
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Grupos de Permissão",
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'is_active', 'is_staff', 'is_superuser', 'groups')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['nome_completo'].initial = self.instance.get_full_name().strip() or self.instance.first_name
            try:
                mil = self.instance.profile.militar
                self.fields['militar'].initial = mil.pk if mil else None
            except Exception:
                pass

    def save(self, commit=True):
        user = super().save(commit=False)
        nome = self.cleaned_data.get('nome_completo', '').strip()
        militar_selecionado = self.cleaned_data.get('militar')
        if not nome and militar_selecionado:
            nome = (militar_selecionado.nome_completo or '').strip()
        partes = nome.split()
        user.first_name = partes[0] if partes else ''
        user.last_name  = ' '.join(partes[1:]) if len(partes) > 1 else ''
        if commit:
            user.save()
            self.save_m2m()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.militar = militar_selecionado
            profile.save()
        return user


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
        fields = ('prazo_defesa_dias', 'prazo_defesa_minutos')
