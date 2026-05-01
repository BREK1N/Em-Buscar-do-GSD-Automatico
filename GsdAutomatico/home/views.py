from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import View, DetailView, CreateView, UpdateView, DeleteView
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.messages import get_messages
from django.urls import reverse_lazy, reverse
from django.http import HttpResponseForbidden
from django.db.models import Q

from caixa_entrada.models import Mensagem
from login.models import UserProfile
from .models import CarouselSlide, Tutorial, TutorialImage, TutorialAttachment
from .forms import (
    ProfileEditForm, CarouselSlideForm, TutorialForm,
    TutorialImageForm, TutorialAttachmentForm,
)
from .permissions import can_manage_home_content

APP_GROUPS = {
    'Ouvidoria':         ('Ouvidoria:index',       'Ouvidoria'),
    'Informatica':       ('informatica:dashboard', 'Informática'),
    'S1':                ('Secao_pessoal:index',   'Seção de Pessoal'),
    'seção de operação': ('Secao_operacoes:index', 'Seção de Operações'),
}

APP_ICONS = {
    'Ouvidoria': '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>',
    'Informatica': '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M9 17.25v1.007a3 3 0 01-.879 2.122L7.5 21h9l-.621-.621A3 3 0 0115 18.257V17.25m6-12V15a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 15V5.25m18 0A2.25 2.25 0 0018.75 3H5.25A2.25 2.25 0 003 5.25m18 0V12a2.25 2.25 0 01-2.25 2.25H5.25A2.25 2.25 0 013 12V5.25" /></svg>',
    'S1': '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z" /></svg>',
    'seção de operação': '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="1.5" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" d="M3.75 12h16.5m-16.5 3.75h16.5M3.75 19.5h16.5M5.625 4.5h12.75a1.875 1.875 0 010 3.75H5.625a1.875 1.875 0 010-3.75z" /></svg>',
}


def _get_available_apps(user):
    user_group_names = set(user.groups.values_list('name', flat=True))
    apps = []
    for group_name, (url_name, display_name) in APP_GROUPS.items():
        if user.is_superuser or group_name in user_group_names:
            apps.append({
                'url_name': url_name,
                'display_name': display_name,
                'icon': APP_ICONS.get(group_name, ''),
            })
    return apps


class HomeInboxView(LoginRequiredMixin, View):
    """Redireciona para a caixa de entrada com contexto 'home' para usar template neutro."""
    def get(self, request):
        request.session['caixa_entrada_secao'] = 'home'
        from django.urls import reverse
        return redirect(reverse('caixa_entrada:inbox'))


class TutorialListView(LoginRequiredMixin, View):
    def get(self, request):
        q = request.GET.get('q', '').strip()
        tutorials = Tutorial.objects.filter(published=True).select_related('author').prefetch_related('attachments')
        if q:
            tutorials = tutorials.filter(Q(title__icontains=q) | Q(category__icontains=q))
        tutorials = tutorials.order_by('-created_at')
        return render(request, 'home/tutorial_list.html', {
            'tutorials': tutorials,
            'q': q,
            'can_manage': can_manage_home_content(request.user),
        })


class HomeDashboardView(LoginRequiredMixin, View):
    def get(self, request):
        # Descarta mensagens flash de outras seções para não poluir a home
        list(get_messages(request))

        user = request.user
        available_apps = _get_available_apps(user)

        unread_msgs = (
            Mensagem.objects
            .filter(destinatarios=user, eh_rascunho=False)
            .exclude(excluida_por=user)
            .exclude(lida_por=user)
            .select_related('remetente')
            .order_by('-data_envio')[:5]
        )

        slides = CarouselSlide.objects.filter(active=True).order_by('order')
        tutorials = Tutorial.objects.filter(published=True).select_related('author').prefetch_related('attachments')[:9]

        try:
            profile = user.profile
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=user)

        context = {
            'available_apps': available_apps,
            'unread_msgs': unread_msgs,
            'slides': slides,
            'tutorials': tutorials,
            'profile': profile,
            'can_manage': can_manage_home_content(user),
        }
        return render(request, 'home/dashboard.html', context)


class ProfileEditView(LoginRequiredMixin, View):
    def get(self, request):
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=request.user)
        form = ProfileEditForm(instance=profile, user=request.user)
        return render(request, 'home/profile_edit.html', {'form': form})

    def post(self, request):
        try:
            profile = request.user.profile
        except UserProfile.DoesNotExist:
            profile = UserProfile.objects.create(user=request.user)
        form = ProfileEditForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Perfil atualizado com sucesso.')
            return redirect('home:index')
        return render(request, 'home/profile_edit.html', {'form': form})


class _ManageRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not can_manage_home_content(request.user):
            return HttpResponseForbidden('Acesso restrito à Informática.')
        return super().dispatch(request, *args, **kwargs)


class TutorialDetailView(LoginRequiredMixin, DetailView):
    model = Tutorial
    template_name = 'home/tutorial_detail.html'
    context_object_name = 'tutorial'

    def get_queryset(self):
        qs = super().get_queryset()
        if not can_manage_home_content(self.request.user):
            qs = qs.filter(published=True)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['can_manage'] = can_manage_home_content(self.request.user)
        return ctx


def _save_inline_attachments(request, tutorial):
    """Processa attach_file_N / attach_name_N enviados pelo tutorial_form."""
    i = 0
    while True:
        file_key = f'attach_file_{i}'
        name_key = f'attach_name_{i}'
        if file_key not in request.FILES:
            break
        f = request.FILES[file_key]
        name = request.POST.get(name_key, f.name)
        if f and name:
            TutorialAttachment.objects.create(tutorial=tutorial, file=f, name=name)
        i += 1


class TutorialCreateView(_ManageRequiredMixin, View):
    def get(self, request):
        form = TutorialForm()
        return render(request, 'home/tutorial_form.html', {'form': form, 'action': 'Criar'})

    def post(self, request):
        form = TutorialForm(request.POST, request.FILES)
        if form.is_valid():
            tutorial = form.save(commit=False)
            tutorial.author = request.user
            tutorial.save()
            _save_inline_attachments(request, tutorial)
            messages.success(request, 'Tutorial criado com sucesso.')
            return redirect('home:tutorial_detail', pk=tutorial.pk)
        return render(request, 'home/tutorial_form.html', {'form': form, 'action': 'Criar'})


class TutorialUpdateView(_ManageRequiredMixin, View):
    def get(self, request, pk):
        tutorial = get_object_or_404(Tutorial, pk=pk)
        form = TutorialForm(instance=tutorial)
        return render(request, 'home/tutorial_form.html', {
            'form': form, 'tutorial': tutorial, 'action': 'Editar'
        })

    def post(self, request, pk):
        tutorial = get_object_or_404(Tutorial, pk=pk)
        form = TutorialForm(request.POST, request.FILES, instance=tutorial)
        if form.is_valid():
            form.save()
            _save_inline_attachments(request, tutorial)
            messages.success(request, 'Tutorial atualizado.')
            return redirect('home:tutorial_detail', pk=tutorial.pk)
        return render(request, 'home/tutorial_form.html', {
            'form': form, 'tutorial': tutorial, 'action': 'Editar'
        })


class TutorialDeleteView(_ManageRequiredMixin, View):
    def post(self, request, pk):
        tutorial = get_object_or_404(Tutorial, pk=pk)
        tutorial.delete()
        messages.success(request, 'Tutorial excluído.')
        return redirect('home:index')


class TutorialImageAddView(_ManageRequiredMixin, View):
    def post(self, request, pk):
        tutorial = get_object_or_404(Tutorial, pk=pk)
        form = TutorialImageForm(request.POST, request.FILES)
        if form.is_valid():
            img = form.save(commit=False)
            img.tutorial = tutorial
            img.save()
            messages.success(request, 'Imagem adicionada.')
        return redirect('home:tutorial_detail', pk=pk)


class TutorialAttachmentAddView(_ManageRequiredMixin, View):
    def post(self, request, pk):
        tutorial = get_object_or_404(Tutorial, pk=pk)
        form = TutorialAttachmentForm(request.POST, request.FILES)
        if form.is_valid():
            att = form.save(commit=False)
            att.tutorial = tutorial
            att.save()
            messages.success(request, 'Anexo adicionado.')
        return redirect('home:tutorial_detail', pk=pk)


class TutorialAttachmentDeleteView(_ManageRequiredMixin, View):
    def post(self, request, pk):
        att = get_object_or_404(TutorialAttachment, pk=pk)
        tutorial_pk = att.tutorial.pk
        att.file.delete(save=False)
        att.delete()
        messages.success(request, 'Anexo removido.')
        return redirect('home:tutorial_detail', pk=tutorial_pk)


class TutorialImageDeleteView(_ManageRequiredMixin, View):
    def post(self, request, pk):
        img = get_object_or_404(TutorialImage, pk=pk)
        tutorial_pk = img.tutorial.pk
        img.image.delete(save=False)
        img.delete()
        messages.success(request, 'Imagem removida.')
        return redirect('home:tutorial_detail', pk=tutorial_pk)


class CarouselManageView(_ManageRequiredMixin, View):
    def get(self, request):
        slides = CarouselSlide.objects.all().order_by('order')
        form = CarouselSlideForm()
        return render(request, 'home/carousel_manage.html', {'slides': slides, 'form': form})

    def post(self, request):
        form = CarouselSlideForm(request.POST, request.FILES)
        if form.is_valid():
            slide = form.save(commit=False)
            slide.created_by = request.user
            slide.save()
            messages.success(request, 'Slide adicionado.')
            return redirect('home:carousel_manage')
        slides = CarouselSlide.objects.all().order_by('order')
        return render(request, 'home/carousel_manage.html', {'slides': slides, 'form': form})


class CarouselSlideDeleteView(_ManageRequiredMixin, View):
    def post(self, request, pk):
        slide = get_object_or_404(CarouselSlide, pk=pk)
        slide.image.delete(save=False)
        slide.delete()
        messages.success(request, 'Slide removido.')
        return redirect('home:carousel_manage')
