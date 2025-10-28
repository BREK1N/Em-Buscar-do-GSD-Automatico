# GsdAutomatico/informatica/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import User, Group
# Importa os modelos de outros apps
from Ouvidoria.models import Militar, Configuracao
from login.models import UserProfile # Modelo do Login

class MilitarForm(forms.ModelForm):
    """
    Formulário para criar e atualizar Militares dentro do app Informatica.
    (Mantém o que já existia)
    """
    class Meta:
        model = Militar
        fields = [
            'posto', 'quad', 'especializacao', 'saram', 'nome_completo',
            'nome_guerra', 'turma', 'situacao', 'om', 'setor', 'subsetor', 'oficial',
        ]
        widgets = {
            'posto': forms.TextInput(attrs={'placeholder': 'Ex: Capitão'}),
            'quad': forms.TextInput(attrs={'placeholder': 'Ex: QOAV'}),
            'especializacao': forms.TextInput(attrs={'placeholder': 'Ex: Aviador'}),
            'saram': forms.NumberInput(attrs={'placeholder': 'Apenas números'}),
            'nome_completo': forms.TextInput(attrs={'placeholder': 'Nome completo do militar'}),
            'nome_guerra': forms.TextInput(attrs={'placeholder': 'Nome de guerra'}),
            'turma': forms.TextInput(attrs={'placeholder': 'Ex: 2024'}),
            'situacao': forms.TextInput(attrs={'placeholder': 'Ex: Ativo'}),
            'om': forms.TextInput(attrs={'placeholder': 'Ex: CINDACTA IV'}),
            'setor': forms.TextInput(attrs={'placeholder': 'Ex: Divisão de Operações'}),
            'subsetor': forms.TextInput(attrs={'placeholder': 'Ex: Seção de Busca e Salvamento'}),
        }
        labels = {
            'saram': 'SARAM',
            'om': 'OM',
            'quad': 'Quadro',
        }

# --- Novos Formulários ---

class InformaticaUserCreationForm(forms.ModelForm): # Alterado para ModelForm
    """ Formulário para criar novos utilizadores na área de informática """
    # --- Alterações ---
    # Remover campos de senha
    # Adicionar campos militar e groups

    militar = forms.ModelChoiceField(
        queryset=Militar.objects.all(),
        required=False, # Associação é opcional
        label="Militar Associado (Opcional)",
        help_text="Associe este utilizador a um militar existente no efetivo.",
        widget=forms.HiddenInput() # Oculto, será preenchido via modal
    )

    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Grupos de Permissão",
        help_text="Os grupos que este utilizador pertence."
    )
    # --- Fim Alterações ---

    class Meta:
        model = User
        fields = ("username", "militar", "groups") # Campos a serem mostrados

    # Sobrescreve o save para definir senha padrão e associar perfil/grupos
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password('12345678') # Define a senha padrão
        if commit:
            user.save()
            # Salva a relação ManyToMany dos grupos APÓS o user ser salvo
            self.save_m2m() # Importante para salvar os grupos selecionados

            # Associa o militar ao UserProfile
            militar_selecionado = self.cleaned_data.get('militar')
            # Garante que o perfil existe ou cria um novo
            profile, created = UserProfile.objects.get_or_create(user=user)
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
        self.fields['comandante_gsd'].queryset = Militar.objects.filter(oficial=True).order_by('posto', 'nome_guerra')
        self.fields['comandante_gsd'].empty_label = "--- Selecione ---"
        self.fields['comandante_bagl'].queryset = Militar.objects.filter(oficial=True).order_by('posto', 'nome_guerra')
        self.fields['comandante_bagl'].empty_label = "--- Selecione ---"

