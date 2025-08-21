from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User, Group
from Ouvidoria.models import Militar
from .models import UserProfile

class CustomUserCreationForm(UserCreationForm):
    militar = forms.ModelChoiceField(
        queryset=Militar.objects.all(),
        required=False,
        label="Militar Associado",
        help_text="Associe este utilizador a um militar existente no efetivo (opcional).",
        # O widget foi alterado para HiddenInput, pois será controlado pelo modal.
        widget=forms.HiddenInput()
    )
    
    grupos = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Permissões de Aplicação",
        help_text="Selecione os aplicativos que este utilizador poderá aceder."
    )

    # A classe Meta foi removida para herdar completamente da UserCreationForm,
    # o que restaura os campos de palavra-passe.

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # Adiciona o utilizador aos grupos selecionados
            user.groups.set(self.cleaned_data['grupos'])
            
            militar_selecionado = self.cleaned_data.get('militar')
            
            # Garante que o perfil existe e associa o militar selecionado
            profile, created = UserProfile.objects.get_or_create(user=user)
            if militar_selecionado:
                profile.militar = militar_selecionado
                profile.save()
        return user
