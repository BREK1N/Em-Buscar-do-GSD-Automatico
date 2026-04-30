import logging
from functools import wraps
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.mixins import UserPassesTestMixin

from ..models import PATD
from ..permissions import has_comandante_access, has_ouvidoria_access, can_finalizar_ouvidoria

logger = logging.getLogger(__name__)

def comandante_redirect(view_func):
    """
    Decorator for views that checks that the user is NOT a comandante,
    redirecting to the comandante dashboard if they are.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if has_comandante_access(request.user) and not request.user.is_superuser:
            return redirect('Ouvidoria:comandante_dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def oficial_responsavel_required(view_func):
    """
    Decorator que verifica se o usuário logado é o oficial responsável pela PATD.
    """
    @wraps(view_func)
    def _wrapped_view(request, pk, *args, **kwargs):
        patd = get_object_or_404(PATD, pk=pk)

        # Superusuário sempre tem acesso
        if request.user.is_superuser:
            return view_func(request, pk, *args, **kwargs)

        # Verifica se o usuário tem um perfil militar e se ele é o oficial responsável
        if (hasattr(request.user, 'profile') and
            request.user.profile.militar and
            request.user.profile.militar == patd.oficial_responsavel):
            return view_func(request, pk, *args, **kwargs)
        else:
            messages.error(request, "Acesso negado. Apenas o oficial apurador designado pode executar esta ação.")
            return redirect('Ouvidoria:patd_detail', pk=pk)
    return _wrapped_view


class OuvidoriaAccessMixin(UserPassesTestMixin):
    """Mixin para Class-Based Views para verificar a permissão de acesso à Ouvidoria."""
    def test_func(self):
        return has_ouvidoria_access(self.request.user)


class ComandanteAccessMixin(UserPassesTestMixin):
    def test_func(self):
        return has_comandante_access(self.request.user)


ouvidoria_required = user_passes_test(has_ouvidoria_access)
comandante_required = user_passes_test(has_comandante_access)
finalizar_ouvidoria_required = user_passes_test(can_finalizar_ouvidoria)
