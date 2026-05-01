from django import forms
from django.contrib.auth.models import User
from login.models import UserProfile
from .models import CarouselSlide, Tutorial, TutorialImage, TutorialAttachment


class ProfileEditForm(forms.ModelForm):
    first_name = forms.CharField(max_length=150, required=False, label='Nome')
    last_name = forms.CharField(max_length=150, required=False, label='Sobrenome')
    email = forms.EmailField(required=False, label='E-mail')

    class Meta:
        model = UserProfile
        fields = ['foto', 'ramal']
        labels = {
            'foto': 'Foto de Perfil',
            'ramal': 'Ramal',
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields['first_name'].initial = self.user.first_name
            self.fields['last_name'].initial = self.user.last_name
            self.fields['email'].initial = self.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        if self.user:
            self.user.first_name = self.cleaned_data['first_name']
            self.user.last_name = self.cleaned_data['last_name']
            self.user.email = self.cleaned_data['email']
            self.user.save()
        if commit:
            profile.save()
        return profile


class CarouselSlideForm(forms.ModelForm):
    class Meta:
        model = CarouselSlide
        fields = ['title', 'subtitle', 'image', 'link_url', 'order', 'active']


class TutorialForm(forms.ModelForm):
    class Meta:
        model = Tutorial
        fields = ['title', 'content', 'cover_image', 'category', 'published']
        widgets = {
            'content': forms.HiddenInput(),
        }


class TutorialImageForm(forms.ModelForm):
    class Meta:
        model = TutorialImage
        fields = ['image', 'caption', 'order']


class TutorialAttachmentForm(forms.ModelForm):
    class Meta:
        model = TutorialAttachment
        fields = ['file', 'name', 'description']
