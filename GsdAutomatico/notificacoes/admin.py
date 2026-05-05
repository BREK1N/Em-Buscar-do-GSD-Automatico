from django.contrib import admin
from .models import Notificacao


@admin.register(Notificacao)
class NotificacaoAdmin(admin.ModelAdmin):
    list_display   = ('usuario', 'tipo', 'titulo', 'lida', 'criado_em')
    list_filter    = ('tipo', 'lida')
    search_fields  = ('titulo', 'usuario__username')
    date_hierarchy = 'criado_em'
    actions        = ['marcar_lida', 'marcar_nao_lida']

    @admin.action(description='Marcar como lida')
    def marcar_lida(self, request, qs):
        qs.update(lida=True)

    @admin.action(description='Marcar como não lida')
    def marcar_nao_lida(self, request, qs):
        qs.update(lida=False)
