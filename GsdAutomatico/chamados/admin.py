from django.contrib import admin
from .models import Chamado, MensagemChamado, AnexoChamado


class MensagemInline(admin.TabularInline):
    model = MensagemChamado
    extra = 0
    readonly_fields = ['autor', 'eh_sistema', 'created_at']


class AnexoInline(admin.TabularInline):
    model = AnexoChamado
    extra = 0


@admin.register(Chamado)
class ChamadoAdmin(admin.ModelAdmin):
    list_display = ['protocolo', 'titulo', 'solicitante', 'atribuido_a', 'status', 'prioridade', 'created_at']
    list_filter = ['status', 'prioridade']
    search_fields = ['protocolo', 'titulo', 'solicitante__username']
    inlines = [MensagemInline]
    readonly_fields = ['protocolo', 'created_at', 'updated_at']
